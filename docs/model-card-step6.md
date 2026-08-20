# STEP 6 Synthetic Attrition Model Card

## Intended use

Demonstrate end-to-end tabular ML engineering on a fully synthetic employee panel: temporal validation,
class imbalance, model comparison, calibration and explainability.

## Out of scope

- real employee-level termination, promotion, compensation or disciplinary decisions;
- mental-health diagnosis or sensitive-attribute inference;
- training on real browsing/search/document histories;
- treating model probability as a causal estimate of resignation intent.

## Target

`attrition_90d = 1` when the synthetic departure event falls within the next three monthly horizons after
a snapshot. Secondary 30d/60d targets are generated for future experiments.

## Evaluation

A purged temporal split keeps three months between train/validation and validation/test to match the
90-day label horizon. Candidate models are selected by validation Average Precision and evaluated once
on the untouched test window. The selected model is then probability-calibrated using the disjoint
validation window.

## Feature policy

`privacy_safe` is the default feature set. Direct synthetic job-search proxies are excluded. The
`synthetic_full` feature set is an ablation experiment only.
