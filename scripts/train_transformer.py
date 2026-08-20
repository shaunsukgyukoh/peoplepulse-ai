from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from peoplepulse.nlp.labels import LABELS
from peoplepulse.nlp.metrics import benchmark_latency, multilabel_metrics


class WorkplaceDataset(Dataset):
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
        item = {k: v.squeeze(0) for k, v in encoded.items()}
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


def predict_probabilities(model, loader, device):
    model.eval()
    probs, truth = [], []
    with torch.inference_mode():
        for batch in loader:
            labels = batch.pop("labels")
            inputs = {k: v.to(device) for k, v in batch.items()}
            logits = model(**inputs).logits
            probs.append(torch.sigmoid(logits).cpu().numpy())
            truth.append(labels.numpy())
    return np.vstack(truth), np.vstack(probs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", default="beomi/KcELECTRA-small-v2022")
    parser.add_argument("--data", default="data/synthetic/nlp/workplace_messages_v01.csv")
    parser.add_argument("--output", default=None)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    safe_name = args.model_name.replace("/", "__")
    out = Path(args.output or f"artifacts/models/{safe_name}")
    out.mkdir(parents=True, exist_ok=True)
    device = choose_device(args.device)
    print(f"device={device} model={args.model_name}")

    df = pd.read_csv(args.data)
    train_df = df[df["split"] == "train"].reset_index(drop=True)
    val_df = df[df["split"] == "val"].reset_index(drop=True)
    test_df = df[df["split"] == "test"].reset_index(drop=True)

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(LABELS),
        id2label={i: label for i, label in enumerate(LABELS)},
        label2id={label: i for i, label in enumerate(LABELS)},
        problem_type="multi_label_classification",
    )
    model.to(device)

    train_ds = WorkplaceDataset(train_df, tokenizer, args.max_length)
    val_ds = WorkplaceDataset(val_df, tokenizer, args.max_length)
    test_ds = WorkplaceDataset(test_df, tokenizer, args.max_length)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size)

    positives = train_df[list(LABELS)].sum(axis=0).to_numpy(dtype=np.float32)
    negatives = len(train_df) - positives
    pos_weight = torch.tensor(
        np.maximum(1.0, negatives / np.maximum(positives, 1.0)),
        device=device,
    )
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    best_f1 = -1.0
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for batch in train_loader:
            labels = batch.pop("labels").to(device)
            inputs = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            logits = model(**inputs).logits
            loss = loss_fn(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            running += float(loss.item())

        y_val, p_val = predict_probabilities(model, val_loader, device)
        val_f1 = float(f1_score(y_val, p_val >= args.threshold, average="macro", zero_division=0))
        epoch_info = {
            "epoch": epoch,
            "train_loss": running / max(len(train_loader), 1),
            "val_macro_f1": val_f1,
        }
        history.append(epoch_info)
        print(epoch_info)
        if val_f1 > best_f1:
            best_f1 = val_f1
            model.config.peoplepulse_model_version = "step3-v1"
            model.config.peoplepulse_base_model = args.model_name
            model.save_pretrained(out)
            tokenizer.save_pretrained(out)

    best_model = AutoModelForSequenceClassification.from_pretrained(out).to(device)
    y_test, p_test = predict_probabilities(best_model, test_loader, device)
    metrics = multilabel_metrics(y_test, p_test, threshold=args.threshold)

    def one(text: str):
        enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=args.max_length)
        enc = {k: v.to(device) for k, v in enc.items()}
        if device.type == "cuda":
            torch.cuda.synchronize()
        with torch.inference_mode():
            probs = torch.sigmoid(best_model(**enc).logits)
        if device.type == "cuda":
            torch.cuda.synchronize()
        return probs.detach().cpu().numpy()

    metrics.update(benchmark_latency(one, test_df["text"].astype(str).tolist()))
    metrics.update({
        "model_name": args.model_name,
        "model_family": "transformer",
        "device": str(device),
        "dataset": args.data,
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "best_val_macro_f1": best_f1,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.lr,
        "history": history,
    })
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
