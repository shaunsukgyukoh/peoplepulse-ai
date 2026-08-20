from __future__ import annotations

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline


def explain_model(
    *,
    model_path: str | Path,
    feature_frame: pd.DataFrame,
    output_dir: str | Path,
    max_rows: int = 500,
) -> pd.DataFrame:
    model = joblib.load(model_path)
    sample = feature_frame.head(max_rows).copy()

    if isinstance(model, Pipeline):
        # Current STEP 6 linear baseline: imputer -> scaler -> LogisticRegression.
        transformed = sample
        for _, transformer in model.steps[:-1]:
            transformed = transformer.transform(transformed)
        final_model = model.steps[-1][1]
        explainer = shap.LinearExplainer(final_model, transformed)
        explanation = explainer(transformed)
        values = np.asarray(explanation.values)
    else:
        explainer = shap.TreeExplainer(model)
        explanation = explainer(sample)
        values = np.asarray(explanation.values)
        if values.ndim == 3:
            values = values[:, :, -1]

    importance = np.mean(np.abs(values), axis=0)
    result = pd.DataFrame({"feature": sample.columns, "mean_abs_shap": importance}).sort_values(
        "mean_abs_shap", ascending=False
    )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result.to_csv(output / "shap_feature_importance.csv", index=False)

    top = result.head(20).sort_values("mean_abs_shap")
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.barh(top["feature"], top["mean_abs_shap"])
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title("STEP 6 synthetic attrition model — global feature importance")
    fig.tight_layout()
    fig.savefig(output / "shap_global_importance.png", dpi=160)
    plt.close(fig)
    return result
