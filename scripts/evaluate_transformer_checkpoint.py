from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from peoplepulse.nlp.labels import LABELS
from peoplepulse.nlp.metrics import benchmark_latency, multilabel_metrics
from peoplepulse.nlp.thresholds import optimize_per_label_thresholds


class EvalDataset(Dataset):
    def __init__(self, df: pd.DataFrame, tokenizer, max_length: int) -> None:
        self.texts = df["text"].astype(str).tolist()
        self.labels = df[list(LABELS)].to_numpy(dtype=np.float32)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int):
        encoded = self.tokenizer(
            self.texts[idx],
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.float32)
        return item


def choose_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def predict_probabilities(model, loader, device: torch.device):
    model.eval()
    probs: list[np.ndarray] = []
    truth: list[np.ndarray] = []
    with torch.inference_mode():
        for batch in loader:
            labels = batch.pop("labels")
            inputs = {key: value.to(device) for key, value in batch.items()}
            logits = model(**inputs).logits
            probs.append(torch.sigmoid(logits).detach().cpu().numpy())
            truth.append(labels.numpy())
    return np.vstack(truth), np.vstack(probs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--data", default="data/synthetic/nlp/workplace_messages_v01.csv")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--grid-min", type=float, default=0.10)
    parser.add_argument("--grid-max", type=float, default=0.90)
    parser.add_argument("--grid-step", type=float, default=0.05)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    if not (model_dir / "config.json").exists():
        raise SystemExit(f"Not a Hugging Face checkpoint: {model_dir}")

    device = choose_device(args.device)
    print(f"device={device} checkpoint={model_dir}")
    if device.type == "cuda":
        print(f"cuda_runtime={torch.version.cuda} gpu={torch.cuda.get_device_name(0)}")

    df = pd.read_csv(args.data)
    val_df = df[df["split"] == "val"].reset_index(drop=True)
    test_df = df[df["split"] == "test"].reset_index(drop=True)

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(device)
    model.eval()

    val_loader = DataLoader(
        EvalDataset(val_df, tokenizer, args.max_length),
        batch_size=args.batch_size,
    )
    test_loader = DataLoader(
        EvalDataset(test_df, tokenizer, args.max_length),
        batch_size=args.batch_size,
    )

    y_val, p_val = predict_probabilities(model, val_loader, device)
    thresholds = optimize_per_label_thresholds(
        y_val,
        p_val,
        labels=LABELS,
        grid_min=args.grid_min,
        grid_max=args.grid_max,
        grid_step=args.grid_step,
    )

    y_test, p_test = predict_probabilities(model, test_loader, device)
    fixed_metrics = multilabel_metrics(y_test, p_test, threshold=0.5)
    tuned_metrics = multilabel_metrics(y_test, p_test, threshold=thresholds)

    def predict_one(text: str):
        encoded = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=args.max_length,
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        if device.type == "cuda":
            torch.cuda.synchronize()
        with torch.inference_mode():
            probs = torch.sigmoid(model(**encoded).logits)
        # CUDA kernels are asynchronous. Synchronize before the timer in
        # benchmark_latency() stops so the measured latency is end-to-end.
        if device.type == "cuda":
            torch.cuda.synchronize()
        return probs.detach().cpu().numpy()

    latency = benchmark_latency(predict_one, test_df["text"].astype(str).tolist())
    model_name = str(
        getattr(
            model.config,
            "peoplepulse_base_model",
            getattr(model.config, "_name_or_path", model_dir.name),
        )
    )
    result = {
        **tuned_metrics,
        **latency,
        "model_name": model_name,
        "model_family": "transformer",
        "device": str(device),
        "cuda_runtime": str(torch.version.cuda) if device.type == "cuda" else None,
        "dataset": args.data,
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "threshold_optimization_split": "val",
        "threshold_grid": {
            "min": args.grid_min,
            "max": args.grid_max,
            "step": args.grid_step,
        },
        "fixed_0_5_metrics": fixed_metrics,
        "latency_method": "single-message; CUDA synchronized when device=cuda",
    }

    (model_dir / "thresholds.json").write_text(
        json.dumps(
            {
                "labels": list(LABELS),
                "thresholds": thresholds,
                "optimized_on": "validation",
                "grid": result["threshold_grid"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (model_dir / "metrics_tuned.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
