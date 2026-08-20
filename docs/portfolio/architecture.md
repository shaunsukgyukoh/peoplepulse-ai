# PeoplePulse AI — Final Architecture

## 1. End-to-End Architecture

```mermaid
flowchart TB
    subgraph Sources[Data Sources]
        Slack[Slack Events API\nwork channels only]
        Excel[Month-end Reports\n3 x .xls/.xlsx]
        Synthetic[Synthetic Portfolio Data]
    end

    subgraph Privacy[Privacy Boundary]
        Mask[PII Masking]
        HMAC[HMAC Pseudonymization]
        Filter[Sensitive / Raw Content Filtering]
        Cohort[Cohort Aggregation\nk-anonymity]
    end

    subgraph Streaming[Real-time NLP]
        Redis[(Redis Streams\nno disk persistence)]
        NLP[KLUE RoBERTa\nLocal CUDA Worker]
        Signal[(PostgreSQL\nDerived NLP Signals)]
    end

    subgraph Batch[Monthly Feature Pipeline]
        Validate[Pandera Validation\nReport Type Detection]
        Feature[7d / 30d / 90d Features\nMonthly Activity Features]
        Store[(Feature Store\nPostgreSQL)]
    end

    subgraph ML[ML / Responsible AI]
        Split[Purged Temporal Split]
        Models[Logistic / XGBoost /\nLightGBM / CatBoost]
        Cal[Calibration + SHAP]
        SynOnly[Synthetic Employee-Level\nEvaluation Only]
    end

    subgraph Product[Product Layer]
        API[FastAPI]
        Dash[Next.js Dashboard]
        SSE[SSE Live Signals]
    end

    subgraph MLOps[MLOps]
        MLflow[MLflow Tracking]
        Evidently[Evidently Drift]
        Prom[Prometheus]
        Grafana[Grafana]
    end

    subgraph Agent[Agentic AI]
        Guard[Deterministic Policy Guard]
        Graph[LangGraph StateGraph]
        Tools[Allowlisted Read-only Tools]
        Ollama[Ollama / qwen3:8b\nLocal LLM]
    end

    Slack --> Mask --> HMAC --> Redis --> NLP --> Signal
    Excel --> Validate --> Filter --> HMAC --> Feature
    Signal --> Feature --> Store
    Synthetic --> Store
    Store --> Split --> Models --> Cal --> SynOnly
    Store --> API
    Signal --> API --> SSE --> Dash
    SynOnly --> API --> Dash
    API --> Prom --> Grafana
    Models --> MLflow
    Store --> Evidently --> Prom
    MLflow --> Prom
    Dash --> Guard --> Graph
    Guard -->|allowed| Graph --> Ollama
    Graph --> Tools --> API
    Tools --> Store
    Tools --> MLflow
    Tools --> Evidently
    Guard -->|blocked| Dash
    Cohort --> Store
```

## 2. Trust Boundaries

| Boundary | Rule |
|---|---|
| Slack raw text | Transient processing only; not durably stored |
| Redis | Persistence disabled for transient masked message payloads |
| Identifiers | HMAC pseudonymization before durable analytics storage |
| Browser/report content | Raw URL path/query, search text and document names are not exposed to the Analyst |
| Production analytics | Department/cohort level only; minimum cohort suppression |
| Employee-level ML | Synthetic portfolio data only |
| Agent | No arbitrary SQL; only allowlisted read-only tools |
| Employment decisions | Hiring, firing, promotion, discipline and compensation recommendations blocked |
| Health inference | Workplace NLP signals are not used for mental-health diagnosis |

## 3. Deployment Topology

- **Windows host:** Ollama + NVIDIA GPU NLP worker when CUDA is needed.
- **Docker Compose:** PostgreSQL, Redis, FastAPI, Next.js, MLflow, Evidently worker, Prometheus and Grafana.
- **Local-only default:** no required paid LLM/cloud API.
- **One-command demo:** `./scripts/portfolio_up.ps1 -Scope synthetic_demo`.

## 4. Why this architecture

1. **Separation of raw and derived data** reduces privacy exposure.
2. **Streaming and batch paths are independent** but converge in one feature store.
3. **Temporal ML validation** avoids random-split leakage for future attrition targets.
4. **Calibration and monitoring** separate ranking quality from probability reliability and production health.
5. **Agent tools are domain APIs, not SQL generation**, reducing prompt-injection and data-access risk.
