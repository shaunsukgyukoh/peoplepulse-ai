$ErrorActionPreference = "Stop"

Write-Host "[1/6] CUDA check"
python scripts/check_cuda.py

Write-Host "[2/6] Calibrate TF-IDF baseline"
python scripts/evaluate_baseline_checkpoint.py

$models = @(
    "artifacts/models/klue__roberta-base",
    "artifacts/models/beomi__KcELECTRA-base",
    "artifacts/models/beomi__KcELECTRA-small-v2022"
)

$step = 3
foreach ($model in $models) {
    if (Test-Path "$model/config.json") {
        Write-Host "[$step/6] Calibrate + CUDA benchmark: $model"
        python scripts/evaluate_transformer_checkpoint.py --model-dir $model --device cuda
    }
    else {
        Write-Warning "Checkpoint not found, skipping: $model"
    }
    $step += 1
}

Write-Host "[6/6] Compare calibrated models"
python scripts/compare_nlp_models.py

Write-Host "[OK] STEP 3.1 evaluation complete"
