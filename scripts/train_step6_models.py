from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from peoplepulse.ml.experiment import run_experiment
from peoplepulse.ml.safeguards import require_synthetic_training_source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/synthetic/ml/step6_attrition_panel.csv")
    parser.add_argument("--target", default="attrition_90d", choices=["attrition_30d", "attrition_60d", "attrition_90d"])
    parser.add_argument("--output-dir", default="artifacts/ml/step6")
    parser.add_argument(
        "--feature-sets",
        nargs="+",
        default=["privacy_safe", "synthetic_full"],
        choices=["privacy_safe", "synthetic_full"],
    )
    args = parser.parse_args()

    path = require_synthetic_training_source(args.data)
    frame = pd.read_csv(path)
    results = []
    for feature_set in args.feature_sets:
        result = run_experiment(
            frame,
            feature_set=feature_set,
            target=args.target,
            output_dir=args.output_dir,
        )
        results.append({
            "feature_set": feature_set,
            "selected_model": result.selected_model,
            "output_dir": str(result.output_dir),
        })
        print(f"[OK] {feature_set}: selected={result.selected_model}")

    comparison = []
    for item in results:
        report = json.loads((Path(item["output_dir"]) / "evaluation.json").read_text(encoding="utf-8"))
        comparison.append(
            {
                "feature_set": item["feature_set"],
                "selected_model": item["selected_model"],
                "average_precision": report["test_calibrated"]["average_precision"],
                "pr_auc_trapezoid": report["test_calibrated"]["pr_auc_trapezoid"],
                "roc_auc": report["test_calibrated"]["roc_auc"],
                "brier_score": report["test_calibrated"]["brier_score"],
                "recall_at_top_10pct": report["test_calibrated"]["recall_at_top_10pct"],
            }
        )
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "feature_set_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    pd.DataFrame(comparison).to_csv(output / "feature_set_comparison.csv", index=False)


if __name__ == "__main__":
    main()
