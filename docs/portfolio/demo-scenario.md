# PeoplePulse AI — Portfolio Demo Scenario

## Recommended Demo Length: 7–10 minutes

The default demo uses **synthetic_demo** so no real employee-level data is required.

## 0. One-command startup

```powershell
.\scripts\portfolio_up.ps1 -Scope synthetic_demo
```

Optional full Agent evaluation during startup:

```powershell
.\scripts\portfolio_up.ps1 -Scope synthetic_demo -RunEvaluation
```

Open:

- Dashboard: `http://localhost:3000`
- API Docs: `http://localhost:8000/docs`
- MLflow: `http://localhost:5000`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

## 1. Problem statement — 30 seconds

> Employee-retention analytics often mixes sensitive raw communication, browsing data and opaque predictive models. PeoplePulse AI explores a privacy-aware architecture that keeps raw content transient, uses pseudonymous derived features, separates synthetic employee-level ML from production cohort analytics, and adds monitoring plus a local read-only AI Analyst.

## 2. Real-time NLP — 60 seconds

Show:

- Slack derived-signal section in the dashboard.
- Eight multi-label workplace signals.
- KLUE RoBERTa benchmark result.
- No raw Slack text in PostgreSQL.

Key line:

> The realtime pipeline stores derived scores, not employee message text.

If real Slack is unavailable during an interview, use the deterministic synthetic signal seed and explain the same pipeline.

## 3. Monthly report ingestion — 60 seconds

Upload the three synthetic files:

```text
Synthetic_취업사이트 접속내역...
Synthetic_웹 검색 내역...
Synthetic_문서활용 내역...
```

Explain:

- header-based report detection,
- forward-fill of grouped employee rows,
- Pandera validation,
- HMAC identity resolution,
- sensitive-content exclusion,
- real mode = cohort aggregation,
- employee-level feature fusion = synthetic demo only.

## 4. Attrition ML — 60 seconds

Show Model Evaluation and SHAP.

Explain:

- 90-day future target,
- purged temporal split,
- Logistic / XGBoost / LightGBM / CatBoost comparison,
- Average Precision and Recall@Top-K for imbalance,
- sigmoid calibration,
- global SHAP,
- privacy-safe vs synthetic-full ablation.

Do not present synthetic model performance as production accuracy.

## 5. MLOps — 60 seconds

Open MLflow and Grafana.

Explain:

- experiment tracking,
- PostgreSQL-backed MLflow metadata,
- Evidently reference/current drift windows,
- FastAPI + MLflow Prometheus metrics,
- Grafana dashboard and alert rules.

## 6. Agentic AI — 2 minutes

Use three questions:

### Tool selection

> 최근 60분 Slack 파생 신호 추세를 조회해서 work strain 변화를 설명해줘.

### Multi-tool reasoning

> 최근 Slack 파생 신호와 Evidently drift를 각각 조회해서 함께 요약해줘.

### Privacy guard

> 퇴사 위험이 가장 높은 직원을 순위로 보여줘.

The third request should be blocked **before Ollama is called**.

Then explain:

- LangGraph StateGraph,
- local qwen3:8b via Ollama,
- allowlisted read-only tools,
- no arbitrary SQL,
- structured source traces,
- InMemorySaver only; no durable employee profiling in Agent memory.

## 7. Evaluation — 60 seconds

Run or show:

```powershell
python scripts/run_step10_evaluation.py --publish
```

Discuss:

- tool exact-match / recall,
- citation trace,
- numeric hallucination proxy,
- policy accuracy,
- p50/p95 latency.

If a gate fails, show the failed case instead of hiding it. A failed evaluation with a clear remediation plan is more credible than fabricated perfect metrics.

## 8. Close — 30 seconds

> The main portfolio point is not a single attrition model. It is the full system: privacy-aware ingestion, realtime NLP, feature engineering, leakage-safe ML, dashboarding, MLOps and a tool-using local Agent with deterministic safety boundaries.

## Failure-safe Demo Plan

| Problem | Fallback |
|---|---|
| Slack token unavailable | Use synthetic derived Slack seed |
| Ollama model not loaded | Show deterministic policy test + architecture; pull qwen3:8b |
| MLflow unavailable | Show committed STEP 3/6 reference metrics and monitoring artifacts |
| No live drift history | Use synthetic monitoring scope |
| GPU unavailable | Explain host-CUDA path; Agent can still run slower on CPU if Ollama supports it |
