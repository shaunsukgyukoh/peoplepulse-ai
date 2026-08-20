# PeoplePulse AI — Portfolio Evidence Summary

## Reproducible evidence already committed

- STEP 3 synthetic NLP benchmark: `klue/roberta-base` Macro-F1 **0.799**, p95 **7.26 ms** on `cuda`.
- STEP 6 synthetic attrition temporal test: AP **0.1238**, ROC-AUC **0.6988**, Recall@Top10% **0.2683**.
- STEP 10 deterministic privacy/policy dataset: 36 cases, required gate 100%.

## Live local Agent evaluation

Live tool/citation/hallucination/latency metrics are not committed yet.
Run `python scripts/run_step10_evaluation.py --publish` on the demo machine after Ollama and the portfolio stack are healthy.

## Evidence discipline

- Synthetic benchmark numbers are labeled synthetic.
- No live Agent score is fabricated before local measurement.
- Failed evaluation gates should be kept visible and discussed with the corresponding failed cases.
