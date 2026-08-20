# Portfolio Final Checklist

## Repository

- [ ] Public repository contains no `.env`, tokens or real employee files.
- [ ] `git status` is clean before demo.
- [ ] README screenshots/results correspond to actually measured runs.
- [ ] Synthetic vs production-safe behavior is clearly labeled.
- [ ] Generated model/evaluation artifacts are ignored unless intentionally published.

## Reproducibility

- [ ] `python scripts/check_step10_portfolio.py` passes.
- [ ] `python scripts/run_step10_policy_eval.py` = 100%.
- [ ] `.\scripts\portfolio_up.ps1 -Scope synthetic_demo` succeeds on a clean Docker state.
- [ ] Dashboard, API, MLflow, Prometheus and Grafana URLs open.
- [ ] Agent `/health` sees the configured Ollama model.
- [ ] `.\scripts\portfolio_down.ps1` stops containers without deleting volumes.

## Evaluation

- [ ] Run `python scripts/run_step10_evaluation.py --publish` on the demo machine.
- [ ] Review failed cases manually.
- [ ] Do not hide failed acceptance gates.
- [ ] Record GPU/model/Python environment alongside results when presenting latency.
- [ ] Explain that hallucination is a numeric-grounding proxy, not perfect semantic detection.

## Demo

- [ ] 7–10 minute scenario rehearsed.
- [ ] Synthetic report files ready.
- [ ] Ollama `qwen3:8b` already pulled.
- [ ] Docker images prebuilt if interview network is unreliable.
- [ ] Fallback demo prepared for Slack/Ollama/MLOps outage.

## Interview

- [ ] 30-second pitch memorized conceptually, not word-for-word.
- [ ] Can draw the architecture from memory.
- [ ] Can explain three trade-offs: privacy vs signal, accuracy vs latency, ranking vs calibration.
- [ ] Can explain one failure/debugging story end-to-end.
- [ ] Can state limitations without underselling the engineering work.
