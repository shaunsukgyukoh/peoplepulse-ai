# STEP 6 — Synthetic Attrition ML Architecture

## Scope boundary

STEP 6 is an **employee-level synthetic portfolio experiment only**. The real-data path from STEP 4/5
remains department/cohort aggregated and is not accepted by the training scripts.

## Pipeline

```text
Synthetic monthly employee panel
        |
        v
Target engineering
attrition within 30 / 60 / 90 days
        |
        v
Purged temporal split
Train -> 3-month gap -> Validation -> 3-month gap -> Test
        |
        +-------------------------------+
        |                               |
privacy_safe features             synthetic_full ablation
(no direct job-search proxies)    (synthetic-only comparison)
        |                               |
        v                               v
Logistic Regression / XGBoost / LightGBM / CatBoost
        |
validation Average Precision model selection
        |
Sigmoid probability calibration on disjoint validation window
        |
        v
Untouched temporal test window
        |
PR-AUC / Average Precision / ROC-AUC / Brier / ECE / Recall@Top-K
        |
        v
SHAP global explanation of selected tree model
```

## Leakage controls

- identifiers and snapshot month are not model features;
- departure date / months-to-departure are never features;
- the 90-day target uses three-month purge gaps between train, validation and test windows;
- model selection happens on validation only;
- probability calibration uses validation only;
- the test window is held out until final evaluation.

## Privacy / governance experiment

The default `privacy_safe` model excludes direct job-search proxies (`job_site_*`, `web_search_*`,
after-hours/weekend search ratios). The `synthetic_full` model exists only as an ablation to quantify
how much apparently useful but intrusive intent-proxy data changes synthetic performance.
