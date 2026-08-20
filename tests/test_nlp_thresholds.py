import numpy as np

from peoplepulse.nlp.labels import LABELS
from peoplepulse.nlp.thresholds import apply_thresholds, optimize_per_label_thresholds


def test_apply_per_label_thresholds() -> None:
    probs = np.array([[0.6, 0.4, 0.7, 0.2, 0.5, 0.6, 0.3, 0.8]])
    thresholds = {label: 0.5 for label in LABELS}
    thresholds["neutral"] = 0.3
    pred = apply_thresholds(probs, thresholds)
    assert pred.shape == probs.shape
    assert pred[0, 0] == 1
    assert pred[0, 1] == 1
    assert pred[0, 3] == 0


def test_optimizer_uses_validation_probabilities() -> None:
    y_true = np.array([[0] * len(LABELS), [1] * len(LABELS)])
    y_prob = np.array([[0.2] * len(LABELS), [0.4] * len(LABELS)])
    thresholds = optimize_per_label_thresholds(
        y_true,
        y_prob,
        grid_min=0.1,
        grid_max=0.9,
        grid_step=0.1,
    )
    assert set(thresholds) == set(LABELS)
    assert all(0.1 <= value <= 0.9 for value in thresholds.values())
