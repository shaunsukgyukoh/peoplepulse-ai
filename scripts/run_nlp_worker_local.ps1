$ErrorActionPreference = "Stop"

$env:NLP_BACKEND = "transformer"
$env:NLP_MODEL_PATH = "artifacts/models/selected"
$env:NLP_DEVICE = "cuda"
$env:POSTGRES_HOST = "localhost"
$env:REDIS_HOST = "localhost"
$env:NLP_REDIS_SOCKET_TIMEOUT_SECONDS = "15"

Write-Host "PeoplePulse STEP 3.2 local CUDA worker"
python scripts/check_cuda.py
python -m peoplepulse.nlp.worker
