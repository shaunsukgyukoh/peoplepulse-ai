# STEP 3 — Real-time Korean workplace NLP

## Goal

Turn PII-masked Slack messages in Redis into transient, message-level linguistic signals using a reproducible NLP experiment pipeline. This stage does **not** diagnose mental health and is not an employment-decision engine.

## Labels

- `satisfied`: explicit positive evaluation / appreciation about work or support
- `neutral`: ordinary factual work communication
- `frustrated`: blocked, repeated inconvenience, irritation without strong anger
- `angry`: strongly expressed anger toward a situation/process
- `dissatisfied`: negative evaluation of work/process/organization
- `overloaded`: excessive workload, deadline pressure, insufficient capacity
- `conflict`: disagreement/tension in work interaction
- `disengaged`: low engagement / distancing from work; **not** a mental-health diagnosis

The task is multi-label. `neutral` is treated as a fallback and suppressed when a non-neutral score crosses the runtime threshold.

## Runtime data flow

```text
Slack listener
  -> Redis Stream peoplepulse:slack-events
  -> Consumer Group peoplepulse:nlp-workers
  -> local predictor
  -> PostgreSQL features.message_nlp_signal (scores only)
  -> Redis Stream peoplepulse:nlp-results (derived scores only)
  -> XACK + XDEL transient Slack queue entry
```

PostgreSQL never stores the message text. The worker acknowledges/deletes the transient queue entry only after the derived result is persisted. The database `event_id` primary key makes retries idempotent.

## Portfolio experiment ladder

1. TF-IDF (word + char n-grams) + One-vs-Rest Logistic Regression
2. `beomi/KcELECTRA-small-v2022`: efficiency candidate for real-time local inference
3. `beomi/KcELECTRA-base`: noisy/conversational Korean accuracy candidate
4. `klue/roberta-base`: general Korean NLU reference candidate

Primary selection metric: **Macro-F1** because all signal labels should matter, not just frequent classes. Secondary metrics: Micro-F1, per-label F1, macro precision/recall, subset accuracy, Hamming loss, mean/p95 single-message latency.

## Dataset policy

`data/synthetic/nlp/workplace_messages_v01.csv` is a synthetic portfolio dataset. It is for pipeline validation and model-comparison mechanics, **not evidence that the model is accurate on real employees**. A production-quality study requires a separately governed, consented/anonymized, human-labeled dataset and a split that prevents person/thread leakage.


## STEP 3.1 evaluation correction

The local Windows/NVIDIA environment uses an explicitly installed CUDA 12.1 PyTorch wheel.
Model evaluation now separates training from operating-point selection: per-label decision thresholds are tuned on validation data only, then frozen for test evaluation. CUDA single-message latency is measured with explicit synchronization so asynchronous kernel execution does not under-report wall-clock latency.
