from __future__ import annotations

from collections.abc import Mapping

from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


def candidate_models(*, positive_weight: float, random_state: int = 42) -> Mapping[str, object]:
    return {
        "logistic_regression": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        C=1.0,
                        class_weight="balanced",
                        max_iter=2000,
                        solver="lbfgs",
                        random_state=random_state,
                    ),
                ),
            ]
        ),
        "xgboost": XGBClassifier(
            n_estimators=350,
            max_depth=4,
            learning_rate=0.04,
            min_child_weight=3,
            subsample=0.85,
            colsample_bytree=0.80,
            reg_lambda=1.2,
            reg_alpha=0.05,
            scale_pos_weight=max(1.0, positive_weight),
            eval_metric="logloss",
            n_jobs=4,
            random_state=random_state,
            tree_method="hist",
        ),
        "lightgbm": LGBMClassifier(
            n_estimators=350,
            learning_rate=0.04,
            num_leaves=31,
            max_depth=-1,
            min_child_samples=30,
            subsample=0.85,
            colsample_bytree=0.80,
            reg_lambda=1.0,
            class_weight="balanced",
            random_state=random_state,
            n_jobs=4,
            verbosity=-1,
        ),
        "catboost": CatBoostClassifier(
            iterations=350,
            depth=6,
            learning_rate=0.04,
            loss_function="Logloss",
            eval_metric="PRAUC",
            auto_class_weights="Balanced",
            random_seed=random_state,
            verbose=False,
            allow_writing_files=False,
            thread_count=4,
        ),
    }
