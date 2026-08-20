# STEP 9 — Local Analyst Agent Architecture

## Goal

Add an agentic analytics layer without giving the LLM arbitrary database access or exposing raw employee content.

```text
Next.js Analyst Chat
        |
        v
FastAPI /api/v1/agent/chat
        |
        +--> deterministic policy guard
        |
        v
LangGraph StateGraph
  analyst -> tools -> analyst
        |
        v
ChatOllama
host.docker.internal:11434
        |
        +-- get_executive_overview
        +-- get_slack_signal_trend
        +-- get_feature_store_cohort_summary
        +-- get_monitoring_drift_summary
        +-- get_retention_model_evaluation
        +-- get_shap_global_importance
        +-- get_nlp_model_performance
        +-- get_mlflow_experiments
        +-- synthetic_demo only: get_synthetic_employee_snapshot
```

## Privacy boundary

- No arbitrary SQL tool.
- No raw Slack-message, raw search-query, or raw document-name tool.
- Production `aggregate` scope only exposes cohort-safe analytics.
- Employee-level lookup exists only for generated `demo-*` keys in `synthetic_demo`.
- Employment decisions (hire/fire/discipline/promotion/compensation) are blocked before LLM invocation.
- Work-message NLP signals are not mental-health or psychological diagnoses.
- Synthetic attrition metrics and SHAP explanations are explicitly portfolio-only.

## Memory

STEP 9 uses LangGraph `InMemorySaver` for short-lived demo conversation threads. It is intentionally not long-term employee memory. Persistent agent memory can be added later with a PostgreSQL checkpointer if needed, but should not be used to accumulate employee profiles.
