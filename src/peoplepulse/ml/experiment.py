from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from peoplepulse.ml.calibration import calibrate_fitted_model
from peoplepulse.ml.features import feature_columns
from peoplepulse.ml.metrics import binary_metrics, calibration_points
from peoplepulse.ml.models import candidate_models
from peoplepulse.ml.split import purged_month_split


@dataclass(frozen=True)
class ExperimentResult:
    selected_model: str
    feature_set: str
    output_dir: Path


def _positive_weight(y: pd.Series) -> float:
    positives = int(y.sum())
    negatives = int(len(y) - positives)
    return negatives / max(1, positives)


def run_experiment(
    frame: pd.DataFrame,
    *,
    feature_set: str,
    target: str = "attrition_90d",
    output_dir: str | Path = "artifacts/ml/step6",
    random_state: int = 42,
) -> ExperimentResult:
    columns = feature_columns(feature_set)
    missing = [column for column in [*columns, target, "snapshot_month"] if column not in frame]
    if missing:
        raise ValueError(f"Missing experiment columns: {missing}")

    split = purged_month_split(frame, purge_months=3)
    train = split.train
    validation = split.validation
    test = split.test
    x_train, y_train = train[columns], train[target].astype(int)
    x_val, y_val = validation[columns], validation[target].astype(int)
    x_test, y_test = test[columns], test[target].astype(int)
    if min(int(y_train.sum()), int(y_val.sum()), int(y_test.sum())) == 0:
        raise RuntimeError("Every temporal split must contain at least one positive target")

    output = Path(output_dir) / feature_set
    output.mkdir(parents=True, exist_ok=True)

    model_rows: list[dict[str, object]] = []
    fitted: dict[str, object] = {}
    for name, estimator in candidate_models(
        positive_weight=_positive_weight(y_train), random_state=random_state
    ).items():
        started = time.perf_counter()
        estimator.fit(x_train, y_train)
        fit_seconds = time.perf_counter() - started
        val_probability = np.asarray(estimator.predict_proba(x_val))[:, 1]
        metrics = binary_metrics(y_val.to_numpy(), val_probability)
        row: dict[str, object] = {
            "model": name,
            "feature_set": feature_set,
            "fit_seconds": float(fit_seconds),
            **metrics,
        }
        model_rows.append(row)
        fitted[name] = estimator

    leaderboard = pd.DataFrame(model_rows).sort_values(
        ["average_precision", "brier_score"], ascending=[False, True]
    )
    leaderboard.to_csv(output / "validation_leaderboard.csv", index=False)
    (output / "validation_leaderboard.json").write_text(
        leaderboard.to_json(orient="records", indent=2), encoding="utf-8"
    )
    selected_name = str(leaderboard.iloc[0]["model"])
    selected = fitted[selected_name]

    raw_test_probability = np.asarray(selected.predict_proba(x_test))[:, 1]
    calibrated = calibrate_fitted_model(selected, x_val, y_val)
    calibrated_test_probability = np.asarray(calibrated.predict_proba(x_test))[:, 1]

    raw_metrics = binary_metrics(y_test.to_numpy(), raw_test_probability)
    calibrated_metrics = binary_metrics(y_test.to_numpy(), calibrated_test_probability)
    report = {
        "selected_model": selected_name,
        "feature_set": feature_set,
        "target": target,
        "selection_metric": "validation average_precision",
        "split": split.metadata,
        "train_positive_rate": float(y_train.mean()),
        "validation_positive_rate": float(y_val.mean()),
        "test_positive_rate": float(y_test.mean()),
        "test_raw": raw_metrics,
        "test_calibrated": calibrated_metrics,
        "calibration_method": "sigmoid_on_disjoint_validation_window",
        "feature_columns": columns,
    }
    (output / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "calibration_points.json").write_text(
        json.dumps(
            {
                "raw": calibration_points(y_test.to_numpy(), raw_test_probability),
                "calibrated": calibration_points(y_test.to_numpy(), calibrated_test_probability),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    predictions = test[["canonical_employee_id_hash", "department_id_hash", "snapshot_month", target]].copy()
    predictions["raw_probability"] = raw_test_probability
    predictions["calibrated_probability"] = calibrated_test_probability
    predictions.to_csv(output / "test_predictions.csv", index=False)

    joblib.dump(selected, output / "selected_base_model.joblib")
    joblib.dump(calibrated, output / "selected_calibrated_model.joblib")
    (output / "feature_manifest.json").write_text(
        json.dumps(
            {
                "feature_set": feature_set,
                "model_feature_columns": columns,
                "identifiers_not_for_training": [
                    "canonical_employee_id_hash",
                    "department_id_hash",
                    "snapshot_month",
                ],
                "target": target,
                "scope": "synthetic_demo_only",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return ExperimentResult(selected_model=selected_name, feature_set=feature_set, output_dir=output)
