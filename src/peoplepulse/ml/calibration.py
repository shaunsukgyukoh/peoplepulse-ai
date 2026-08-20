from __future__ import annotations

from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator


def calibrate_fitted_model(estimator: object, x_validation, y_validation):
    """Fit a sigmoid calibrator on validation data without refitting the base estimator."""
    calibrated = CalibratedClassifierCV(
        estimator=FrozenEstimator(estimator),
        method="sigmoid",
    )
    calibrated.fit(x_validation, y_validation)
    return calibrated
