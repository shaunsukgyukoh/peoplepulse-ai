import numpy as np

from peoplepulse.nlp.metrics import multilabel_metrics


def test_multilabel_metrics_perfect_prediction():
    y_true = np.array([[1, 0], [0, 1]])
    y_prob = np.array([[0.9, 0.1], [0.1, 0.9]])
    # metrics uses the project label names; pad to 8 columns
    y_true = np.pad(y_true, ((0, 0), (0, 6)))
    y_prob = np.pad(y_prob, ((0, 0), (0, 6)), constant_values=0.1)
    metrics = multilabel_metrics(y_true, y_prob)
    # Unused labels have zero support/F1, so the micro score is the right smoke check here.
    assert metrics["micro_f1"] == 1.0
