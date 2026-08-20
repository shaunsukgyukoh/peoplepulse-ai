# Portfolio Quick Start

## Prerequisites

- Windows 11 / PowerShell
- Docker Desktop
- Python 3.11 virtual environment
- Ollama
- Recommended for the verified local path: NVIDIA RTX 4080 SUPER / CUDA-enabled PyTorch for NLP

## Install Python extras

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[activity,nlp,ml,agent,dev]"
```

Keep the verified CUDA PyTorch wheel if already installed; do not casually replace it through an unrelated dependency install.

## Configure

Copy `.env.example` once and replace local secrets. Never commit `.env`.

Minimum demo requirements:

- non-placeholder `EMPLOYEE_HASH_KEY`
- local PostgreSQL/Redis credentials
- `ACTIVITY_ADMIN_TOKEN`
- `AGENT_OLLAMA_MODEL=qwen3:8b`
- `MLFLOW_WORKERS=1`

Slack tokens are optional for the synthetic portfolio demo.

## One command

```powershell
.\scripts\portfolio_up.ps1 -Scope synthetic_demo
```

With live Agent evaluation:

```powershell
.\scripts\portfolio_up.ps1 -Scope synthetic_demo -RunEvaluation
```

## Stop

```powershell
.\scripts\portfolio_down.ps1
```

Persistent volumes are retained.
