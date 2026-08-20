# STEP 7 — Product Dashboard Architecture

STEP 7 turns the existing ingestion, NLP, feature-store and synthetic ML experiment into a portfolio-grade local product surface.

```text
Browser :3000
   │
   ├── Executive Overview
   ├── Real-time Slack Signal
   ├── Monthly 3-report Upload
   ├── Synthetic Retention Evaluation
   ├── SHAP Global Importance
   └── Model Performance
   │
   ▼
Next.js 16.3 / React 19.2 / TypeScript
   │
   ├── REST fetch ────────────────┐
   └── EventSource (SSE) ────────┤
                                  ▼
                           FastAPI :8000
                                  │
                  ┌───────────────┼────────────────┐
                  ▼               ▼                ▼
             PostgreSQL      STEP 6 artifacts   repo reference metrics
                  │
        derived / audit data only
```

## Real-time path

Slack message text is not returned to the dashboard. The live panel reads only `features.message_nlp_signal` probabilities and inference metadata. FastAPI streams the latest 15-minute aggregate through SSE. The browser keeps an `EventSource` connection and updates the signal cards without polling.

## Dashboard read model

`peoplepulse.dashboard.service.DashboardService` intentionally has read-only responsibilities:

- recent Slack aggregate and 60-minute trend,
- latest three-report batch audit summary,
- department/synthetic activity feature counts,
- NLP candidate benchmark artifact,
- STEP 6 synthetic attrition metrics,
- SHAP global importance artifact.

If local STEP 6 generated artifacts are absent, attrition metrics fall back to the checked-in reference experiment JSON. SHAP fallback is rank-only; it does **not** fabricate magnitude values.

## Privacy boundary

Production-oriented surfaces expose organization/cohort signals only. The attrition evaluation section is visibly labelled `SYNTHETIC DEMO ONLY`. No endpoint returns raw Slack text, raw search terms, document titles, filenames, URLs, or real individual attrition probabilities.

## Frontend stack

- Next.js 16.3.1 App Router
- React 19.2
- TypeScript
- Tailwind CSS 4.3
- Apache ECharts 6
- native `EventSource` for SSE

## Deployment

All services remain self-hosted with Docker Compose. Dashboard profile publishes `3000`, API publishes `8000`, and the existing PostgreSQL/Redis services remain local. For the verified RTX 4080 SUPER CUDA environment, keep the NLP worker on the Windows host until GPU-containerization is handled in the later MLOps step.
