import numpy as np

from peoplepulse.ml.metrics import binary_metrics


def test_binary_metrics_return_ranking_and_calibration_fields():
    y = np.array([0, 0, 0, 1, 1, 1])
    p = np.array([0.05, 0.10, 0.30, 0.45, 0.80, 0.95])
    result = binary_metrics(y, p)
    assert 0 <= result["average_precision"] <= 1
    assert 0 <= result["brier_score"] <= 1
    assert "recall_at_top_10pct" in result
