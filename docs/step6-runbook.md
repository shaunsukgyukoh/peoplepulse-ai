# STEP 6 Runbook — Synthetic Attrition Modeling

## Install

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[ml,dev]"
```

The `ml` extra is independent from the CUDA-enabled NLP environment and does not reinstall PyTorch.

## Optional database migration

```powershell
docker compose up -d postgres
python scripts/apply_step6_migration.py
```

The STEP 6 ML tables include a database-level `data_scope='synthetic_demo'` constraint.

## Run the complete experiment

```powershell
.\scripts\run_step6_experiment.ps1
```

Equivalent individual commands:

```powershell
python scripts/generate_step6_synthetic_panel.py
python scripts/train_step6_models.py
python scripts/check_step6_results.py
python scripts/explain_step6_model.py --experiment-dir artifacts/ml/step6/privacy_safe
```

## Outputs

```text
data/synthetic/ml/
  step6_attrition_panel.csv
  step6_attrition_panel.summary.json

artifacts/ml/step6/
  feature_set_comparison.csv
  feature_set_comparison.json
  privacy_safe/
    validation_leaderboard.csv
    evaluation.json
    calibration_points.json
    test_predictions.csv
    selected_base_model.joblib
    selected_calibrated_model.joblib
    feature_manifest.json
    shap/
      shap_feature_importance.csv
      shap_global_importance.png
  synthetic_full/
    ...
```

## Primary interpretation

Use **Average Precision / PR-AUC** as the main ranking-quality metrics because attrition is imbalanced.
Report Recall@Top-K to show how much of the synthetic positive class is captured in a constrained review
budget. Use Brier score / ECE to discuss probability calibration. Do not present a calibrated probability
as a causal statement or as evidence that a real employee will resign.


## Dependency preflight and Windows PowerShell failure handling

Before running the experiment, install the STEP 6 optional dependency group in the active `.venv`:

```powershell
python -m pip install -e ".[ml,dev]"
python scripts/check_step6_dependencies.py
```

The experiment runner performs the same dependency preflight automatically. It also checks `$LASTEXITCODE` after every Python command. This is intentional because Windows PowerShell can continue after a native process returns a non-zero exit code even when `$ErrorActionPreference = "Stop"`. Therefore `[OK] STEP 6 experiment complete` is now printed only when every step succeeds.

If `catboost` or `matplotlib` is reported missing, reinstall the project ML extra rather than installing one package at a time, so XGBoost, LightGBM, CatBoost, SHAP and plotting dependencies remain reproducible:

```powershell
python -m pip install -e ".[ml,dev]"
```
