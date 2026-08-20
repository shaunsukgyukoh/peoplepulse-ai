# STEP 3 NLP Experiment Results

## Decision

Production candidate for the portfolio pipeline: **`klue/roberta-base`**.

| Model | Family | Macro-F1 | Micro-F1 | Macro Precision | Macro Recall | P95 latency | Device |
|---|---|---:|---:|---:|---:|---:|---|
| klue/roberta-base | Transformer | 0.7988 | 0.7403 | 0.7315 | 0.9688 | 7.26 ms | CUDA |
| tfidf-logreg | Baseline | 0.5565 | 0.5000 | 0.5929 | 0.7674 | 2.61 ms | CPU |
| beomi/KcELECTRA-base | Transformer | 0.4763 | 0.4254 | 0.3530 | 0.9479 | 6.66 ms | CUDA |
| beomi/KcELECTRA-small-v2022 | Transformer | 0.2628 | 0.2617 | 0.1577 | 0.9167 | 7.81 ms | CUDA |

All rows above use thresholds chosen **only on the validation split** and final metrics on the held-out test split.

## Why KLUE RoBERTa is promoted

- Highest Macro-F1 by a large margin.
- Macro Precision improved while recall remained high after threshold calibration.
- Single-message CUDA P95 latency is comfortably below the 20 ms portfolio promotion budget on the measured local GPU.
- The comparison demonstrates an explicit accuracy/latency decision instead of choosing a model by brand or size.

## Important limitations

- Dataset is synthetic and small (`val=27`, `test=54` in STEP 3.1).
- Per-label threshold estimates can be unstable with only 27 validation examples.
- These numbers are not claims about real employee behavior.
- The model detects linguistic workplace signals only; it must not diagnose mental health.
- Individual scores must not directly trigger hiring, firing, promotion, compensation, or disciplinary decisions. Real deployments should favor aggregate organizational trends and human review.

## Next validation work

1. Expand synthetic coverage and add adversarial/ambiguous workplace messages.
2. Use repeated/multilabel-stratified validation when dataset size permits.
3. Measure label-wise precision/recall and calibration.
4. Add drift monitoring after the streaming pipeline is stable.
