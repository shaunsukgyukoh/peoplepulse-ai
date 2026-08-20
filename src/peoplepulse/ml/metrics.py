from __future__ import annotations

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    auc,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


def ranking_metrics(y_true: np.ndarray, probability: np.ndarray, fraction: float) -> dict[str, float]:
    n = len(y_true)
    k = max(1, int(np.ceil(n * fraction)))
    order = np.argsort(-probability)[:k]
    positives = float(np.sum(y_true))
    found = float(np.sum(y_true[order]))
    return {
        f"precision_at_top_{int(fraction * 100)}pct": found / k,
        f"recall_at_top_{int(fraction * 100)}pct": found / positives if positives else 0.0,
    }


def expected_calibration_error(
    y_true: np.ndarray,
    probability: np.ndarray,
    *,
    bins: int = 10,
) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(y_true)
    error = 0.0
    for left, right in zip(edges[:-1], edges[1:], strict=True):
        include = (probability >= left) & (probability < right if right < 1 else probability <= right)
        if not np.any(include):
            continue
        observed = float(np.mean(y_true[include]))
        predicted = float(np.mean(probability[include]))
        error += float(np.sum(include) / total) * abs(observed - predicted)
    return error


def binary_metrics(
    y_true: np.ndarray,
    probability: np.ndarray,
    *,
    threshold: float = 0.5,
) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=int)
    probability = np.asarray(probability, dtype=float)
    predicted = (probability >= threshold).astype(int)
    precision, recall, _ = precision_recall_curve(y_true, probability)
    result = {
        "rows": int(len(y_true)),
        "positive_rate": float(np.mean(y_true)),
        "average_precision": float(average_precision_score(y_true, probability)),
        "pr_auc_trapezoid": float(auc(recall, precision)),
        "roc_auc": float(roc_auc_score(y_true, probability)) if len(np.unique(y_true)) > 1 else 0.0,
        "brier_score": float(brier_score_loss(y_true, probability)),
        "ece_10bin": float(expected_calibration_error(y_true, probability)),
        "precision_0_5": float(precision_score(y_true, predicted, zero_division=0)),
        "recall_0_5": float(recall_score(y_true, predicted, zero_division=0)),
        "f1_0_5": float(f1_score(y_true, predicted, zero_division=0)),
    }
    for fraction in (0.05, 0.10, 0.20):
        result.update(ranking_metrics(y_true, probability, fraction))
    return result


def calibration_points(
    y_true: np.ndarray,
    probability: np.ndarray,
    *,
    bins: int = 10,
) -> list[dict[str, float]]:
    observed, predicted = calibration_curve(y_true, probability, n_bins=bins, strategy="quantile")
    return [
        {"mean_predicted_probability": float(x), "observed_positive_rate": float(y)}
        for x, y in zip(predicted, observed, strict=True)
    ]
