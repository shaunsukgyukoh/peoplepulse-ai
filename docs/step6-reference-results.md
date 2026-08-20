# STEP 6 Reference Experiment Result

This result is a reproducibility smoke-test on the generated **synthetic** panel, not evidence about real employees.

## Dataset

- rows: 17,332
- synthetic employees: 650
- monthly snapshots: 36
- 90-day positive rate: 0.0637

## Privacy-safe feature set

Validation selected `logistic_regression` by Average Precision. On the untouched temporal test window after probability calibration:

- Average Precision: 0.1238
- trapezoidal PR-AUC: 0.1191
- ROC-AUC: 0.6988
- Brier score: 0.0566
- 10-bin ECE: 0.0604
- Recall@Top10%: 0.2683

The uncalibrated class-balanced model had a very poor Brier score (0.3776); sigmoid calibration reduced it substantially without changing ranking metrics. This is why STEP 6 separates ranking quality from probability calibration.

## Intent-proxy ablation

| Feature set | Selected model | Average Precision | ROC-AUC | Brier | Recall@Top10% |
|---|---|---:|---:|---:|---:|
| privacy_safe | logistic_regression | 0.1238 | 0.6988 | 0.0566 | 0.2683 |
| synthetic_full | logistic_regression | 0.1219 | 0.6927 | 0.0566 | 0.2764 |

In this synthetic run, adding direct job-search/search-activity proxies did **not** improve test Average Precision. That supports keeping the default portfolio model on the less intrusive `privacy_safe` feature set; it does not establish a general causal conclusion.

## SHAP smoke test

The selected linear model was explained with SHAP `LinearExplainer`. The generated runtime report is intentionally ignored by Git; rerun `scripts/explain_step6_model.py` to reproduce it locally.
