from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path("artifacts/ml/step6")
    for feature_set in ("privacy_safe", "synthetic_full"):
        path = root / feature_set / "evaluation.json"
        if not path.exists():
            print(f"[SKIP] {feature_set}: {path} not found")
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        metrics = report["test_calibrated"]
        print(
            f"[OK] {feature_set} model={report['selected_model']} "
            f"AP={metrics['average_precision']:.4f} "
            f"PR-AUC={metrics['pr_auc_trapezoid']:.4f} "
            f"Brier={metrics['brier_score']:.4f} "
            f"Recall@10%={metrics['recall_at_top_10pct']:.4f}"
        )


if __name__ == "__main__":
    main()
