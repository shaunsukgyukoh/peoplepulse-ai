# STEP 1 — Infrastructure Architecture

## Goal

Create a reproducible, zero-additional-cost local foundation for PeoplePulse AI before connecting Slack or processing employee-related data.

## Decisions

1. PostgreSQL is the durable system of record.
2. Redis Streams is the asynchronous event boundary for real-time Slack ingestion.
3. Raw Slack message text is not a durable data product by default.
4. Derived feature and audit namespaces are separated in PostgreSQL.
5. Secrets live in `.env`, which is excluded from Git.
6. Infrastructure runs locally with Docker Compose and named volumes.

## Data boundaries

```text
[External source]
      |
      v
[ingestion boundary] ---- raw content: transient only by default
      |
      v
[privacy processing]
      |
      v
[derived feature layer] ---- durable
      |
      +----> [ML layer]
      |
      +----> [audit layer]
```

## Redis streams reserved now

- `peoplepulse:slack-events`: accepted Slack event envelopes waiting for NLP/privacy processing
- `peoplepulse:nlp-results`: future derived NLP results/events

The Redis structures are reserved in configuration only. STEP 2 will create the producer/consumer behavior.
