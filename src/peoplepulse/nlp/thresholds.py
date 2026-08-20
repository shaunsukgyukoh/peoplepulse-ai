from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from sklearn.metrics import f1_score

from peoplepulse.nlp.labels import LABELS

ThresholdSpec = float | Mapping[str, float]


def threshold_vector(
    thresholds: ThresholdSpec,
    labels: Sequence[str] = LABELS,
) -> np.ndarray:
    if isinstance(thresholds, Mapping):
        return np.asarray([float(thresholds[label]) for label in labels], dtype=np.float32)
    return np.full(len(labels), float(thresholds), dtype=np.float32)


def apply_thresholds(
    y_prob: np.ndarray,
    thresholds: ThresholdSpec,
    labels: Sequence[str] = LABELS,
) -> np.ndarray:
    vector = threshold_vector(thresholds, labels)
    return (np.asarray(y_prob) >= vector.reshape(1, -1)).astype(int)


def optimize_per_label_thresholds(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    labels: Sequence[str] = LABELS,
    grid_min: float = 0.10,
    grid_max: float = 0.90,
    grid_step: float = 0.05,
) -> dict[str, float]:
    """Optimize one threshold per label using validation Macro-F1 components only.

    The test split must never be passed here. Ties are resolved toward 0.5 to avoid
    unnecessarily extreme operating points on a small validation set.
    """
    if y_true.shape != y_prob.shape:
        raise ValueError(f"shape mismatch: y_true={y_true.shape}, y_prob={y_prob.shape}")
    if y_true.shape[1] != len(labels):
        raise ValueError("label count does not match probability columns")
    if grid_step <= 0 or grid_min <= 0 or grid_max >= 1 or grid_min > grid_max:
        raise ValueError("invalid threshold grid")

    grid = np.arange(grid_min, grid_max + grid_step / 2, grid_step)
    optimized: dict[str, float] = {}
    for idx, label in enumerate(labels):
        best_threshold = 0.5
        best_f1 = -1.0
        for candidate in grid:
            pred = (y_prob[:, idx] >= candidate).astype(int)
            score = float(f1_score(y_true[:, idx], pred, zero_division=0))
            if score > best_f1 + 1e-12:
                best_f1 = score
                best_threshold = float(candidate)
            elif abs(score - best_f1) <= 1e-12:
                if abs(float(candidate) - 0.5) < abs(best_threshold - 0.5):
                    best_threshold = float(candidate)
        optimized[str(label)] = round(best_threshold, 4)
    return optimized
