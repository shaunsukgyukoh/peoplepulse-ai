# STEP 9 Runbook

## 1. Install / start Ollama on Windows

Run:

```powershell
.\scripts\setup_step9_ollama.ps1
```

Default model: `qwen3:8b`.

Optional stronger local model if hardware/runtime allows:

```powershell
$env:AGENT_OLLAMA_MODEL="gpt-oss:20b"
ollama pull gpt-oss:20b
```

## 2. Install Python agent dependencies for local development

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[activity,agent,dev]"
```

## 3. Static preflight

```powershell
python scripts/check_step9_agent.py
pytest tests/test_step9_agent_policy.py -q
```

## 4. Run production-safe aggregate agent

```powershell
.\scripts\run_step9_agent.ps1 -Scope aggregate
```

Open:

```text
http://localhost:3000/#analyst
```

## 5. Smoke test

```powershell
.\scripts\smoke_test_step9_agent.ps1
```

## 6. Synthetic demo

Use only with `APP_ENV=development`:

```powershell
.\scripts\run_step9_agent.ps1 -Scope synthetic_demo
```

Example:

```text
demo-001의 2026-07 synthetic feature snapshot과 global SHAP 결과를 구분해서 설명해줘
```

## 7. Troubleshooting

Host Ollama:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
ollama list
```

Container -> host Ollama:

```powershell
docker compose --profile agent exec api python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags').status)"
```

API:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/agent/health
```

Logs:

```powershell
docker compose --profile agent logs --tail=150 api
docker compose --profile agent logs --tail=150 dashboard
```
