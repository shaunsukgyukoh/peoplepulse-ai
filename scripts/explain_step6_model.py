from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from peoplepulse.ml.explain import explain_model
from peoplepulse.ml.safeguards import require_synthetic_training_source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/synthetic/ml/step6_attrition_panel.csv")
    parser.add_argument("--experiment-dir", default="artifacts/ml/step6/privacy_safe")
    args = parser.parse_args()

    source = require_synthetic_training_source(args.data)
    experiment = Path(args.experiment_dir)
    manifest = json.loads((experiment / "feature_manifest.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(source)
    columns = manifest["model_feature_columns"]
    result = explain_model(
        model_path=experiment / "selected_base_model.joblib",
        feature_frame=frame[columns],
        output_dir=experiment / "shap",
    )
    print("[OK] SHAP global importance")
    print(result.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
