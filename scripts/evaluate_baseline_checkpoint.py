from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from peoplepulse.nlp.labels import LABELS
from peoplepulse.nlp.metrics import benchmark_latency, multilabel_metrics
from peoplepulse.nlp.thresholds import optimize_per_label_thresholds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="artifacts/models/tfidf-logreg")
    parser.add_argument("--data", default="data/synthetic/nlp/workplace_messages_v01.csv")
    parser.add_argument("--grid-min", type=float, default=0.10)
    parser.add_argument("--grid-max", type=float, default=0.90)
    parser.add_argument("--grid-step", type=float, default=0.05)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    model_path = model_dir / "model.joblib"
    bundle = joblib.load(model_path)
    pipeline = bundle["pipeline"]
    labels = tuple(bundle.get("labels", LABELS))
    if labels != LABELS:
        raise SystemExit(f"Label order mismatch: {labels}")

    df = pd.read_csv(args.data)
    val_df = df[df["split"] == "val"].reset_index(drop=True)
    test_df = df[df["split"] == "test"].reset_index(drop=True)
    y_val = val_df[list(LABELS)].to_numpy(dtype=int)
    p_val = np.asarray(pipeline.predict_proba(val_df["text"].astype(str).tolist()))
    thresholds = optimize_per_label_thresholds(
        y_val,
        p_val,
        labels=LABELS,
        grid_min=args.grid_min,
        grid_max=args.grid_max,
        grid_step=args.grid_step,
    )

    y_test = test_df[list(LABELS)].to_numpy(dtype=int)
    p_test = np.asarray(pipeline.predict_proba(test_df["text"].astype(str).tolist()))
    fixed_metrics = multilabel_metrics(y_test, p_test, threshold=0.5)
    tuned_metrics = multilabel_metrics(y_test, p_test, threshold=thresholds)

    def predict_one(text: str):
        return pipeline.predict_proba([text])

    latency = benchmark_latency(predict_one, test_df["text"].astype(str).tolist())
    result = {
        **tuned_metrics,
        **latency,
        "model_name": str(bundle.get("model_name", "tfidf-logreg")),
        "model_family": "baseline",
        "device": "cpu",
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
        "latency_method": "single-message CPU wall clock",
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
