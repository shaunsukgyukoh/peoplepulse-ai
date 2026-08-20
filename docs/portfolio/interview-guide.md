# PeoplePulse AI — Interview Guide

## 30-second introduction

> PeoplePulse AI is a self-hosted employee-retention intelligence portfolio that combines realtime Slack NLP, monthly activity-report ingestion, a PostgreSQL feature store, temporal attrition-model evaluation, Next.js dashboards, MLflow/Evidently monitoring, and a local Ollama + LangGraph Analyst Agent. The main design constraint is privacy: raw messages are transient, identifiers are HMAC-pseudonymized, production analytics stay at cohort level, and employee-level attrition modeling is synthetic-only.

## 90-second project explanation

> I built the project as an end-to-end AI product rather than a notebook-only model. Slack events enter through Socket Mode, are PII-masked and queued in non-persistent Redis Streams, then a local KLUE RoBERTa worker creates multi-label workplace signals. Month-end reports are validated against their actual three-file schema, filtered and joined using HMAC identities. Slack 7/30/90-day features and monthly activity features feed a PostgreSQL feature store. For attrition ML I use a 90-day future target with purged temporal splits, compare four model families, evaluate Average Precision and Recall@Top-K, calibrate probabilities and generate SHAP explanations. The product layer is FastAPI + Next.js, MLOps is MLflow + Evidently + Prometheus/Grafana, and the final Analyst Agent uses Ollama and LangGraph but only through allowlisted read-only tools. Requests for individual real-employee risk, raw content, HR decisions or mental-health diagnosis are blocked before the LLM.

## 5-minute technical walkthrough

1. **Ingestion:** Slack realtime + three actual-format monthly reports.
2. **Privacy:** PII masking, HMAC pseudonyms, no Redis persistence, content filtering, cohort suppression.
3. **NLP:** multi-label Korean workplace-signal classification; Macro-F1 + latency model gate.
4. **Features:** daily signals → 7d/30d/90d windows → monthly fusion.
5. **ML:** future 90d target, purge gap, imbalance metrics, calibration, SHAP, ablation.
6. **Product:** FastAPI APIs, SSE and Next.js dashboard.
7. **MLOps:** MLflow experiments, Evidently drift, Prometheus metrics and Grafana.
8. **Agent:** LangGraph + local Ollama, fixed tools, policy guard, source traces.
9. **Evaluation:** tool-call accuracy, citation behavior, numeric grounding proxy, policy accuracy, latency.

## High-value interview questions

### Why multi-label NLP instead of positive/negative sentiment?

A workplace sentence can express overload and frustration at the same time. A single sentiment class loses that structure. I also avoid treating the labels as mental-health diagnoses; they are linguistic work-signal categories only.

### Why Macro-F1?

The eight labels are not equally frequent. Accuracy or Micro-F1 can hide weak minority-label performance. Macro-F1 gives each label equal weight, while latency remains a separate deployment gate.

### Why Redis Streams?

It decouples Slack ingestion from GPU inference, supports consumer groups and pending-message recovery, and allows horizontal workers. Persistence is disabled because masked message text is transient processing data.

### Why HMAC instead of a normal hash?

Employee and Slack identifiers have low entropy and can be dictionary-attacked. A secret-keyed HMAC makes deterministic joins possible without storing the original IDs and without exposing an unsalted lookup surface.

### Why not let the Agent generate SQL?

The database contains sensitive workforce-derived data. An unrestricted SQL tool expands prompt-injection blast radius and makes row-level privacy harder to guarantee. I expose fixed domain tools with predetermined read-only queries instead.

### Why a temporal split for attrition?

The target is future attrition. Random splits allow adjacent months from the same employee and overlapping future windows to leak information. I use chronological train/validation/test windows with a purge gap matching the 90-day target horizon.

### Why calibrate the classifier?

Ranking metrics and probability reliability are different. Class weighting can improve ranking but distort probability values. I evaluate Brier/ECE separately and fit sigmoid calibration using validation data only.

### Why is employee-level retention ML synthetic-only?

An HR-risk model can materially affect people. This portfolio is meant to demonstrate technical architecture without pretending that a synthetic model is appropriate for automated real-employment decisions. Real mode is limited to cohort analytics and human review.

### Why local Ollama?

It keeps the Agent demo self-hosted, avoids sending internal analytics to a third-party LLM API, and demonstrates local tool-calling orchestration. The model is replaceable because LangGraph and tools are separated from the model provider.

### How do you evaluate hallucination?

I do not claim a deterministic script can catch all semantic hallucinations. I measure an auditable proxy: numbers in the answer must appear in the prompt or captured tool evidence, including percent conversion. I combine that with structured source traces, tool-call accuracy and manual review of failed cases.

## Debugging stories worth mentioning

### Next.js Docker runner failure

Production build succeeded, but the runner image failed because `/app/public` did not exist. I separated build failure from packaging failure, added a tracked `public/.gitkeep`, and hardened the Dockerfile with directory creation.

### MLflow unhealthy container

The first issue was startup/migration sequencing. After fixing that, logs showed `prometheus_flask_exporter` missing only when `--expose-prometheus` loaded. I added the optional exporter explicitly plus a build-time import check. This is a good example of using container logs to distinguish health symptoms from the actual dependency failure.

### PowerShell Agent body parsing

FastAPI rejected Korean JSON in the smoke test. The problem was Windows PowerShell request encoding, not LangGraph/Ollama. I encoded the body explicitly as UTF-8 bytes and set `application/json; charset=utf-8`.

## Limitations to state proactively

- NLP and attrition training data are synthetic portfolio evidence, not validated production HR models.
- No causal claim: drift or workplace-signal changes do not prove why attrition changes.
- Policy regex is one deterministic safety layer, not a complete security system.
- InMemorySaver is intentionally non-durable; enterprise conversation memory would need a governed store and retention policy.
- Local single-machine Docker Compose is a portfolio deployment; HA/Kubernetes is not implemented.
- Fairness evaluation requires governed demographic labels that are intentionally absent from this synthetic/public portfolio.

## Strong closing statement

> I would describe the project as a privacy-aware AI platform engineering portfolio. The model is one component; the key work is connecting streaming ingestion, NLP, feature engineering, leakage-safe ML, product APIs, observability and a constrained tool-using Agent into one reproducible system.
