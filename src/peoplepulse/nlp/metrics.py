from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    hamming_loss,
    precision_score,
    recall_score,
)

from peoplepulse.nlp.labels import LABELS
from peoplepulse.nlp.thresholds import ThresholdSpec, apply_thresholds


def multilabel_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: ThresholdSpec = 0.5,
) -> dict:
    y_pred = apply_thresholds(y_prob, threshold, LABELS)
    result = {
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "micro_f1": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "macro_precision": float(
            precision_score(y_true, y_pred, average="macro", zero_division=0)
        ),
        "macro_recall": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "subset_accuracy": float(accuracy_score(y_true, y_pred)),
        "hamming_loss": float(hamming_loss(y_true, y_pred)),
        "per_label_f1": {
            label: float(score)
            for label, score in zip(
                LABELS,
                f1_score(y_true, y_pred, average=None, zero_division=0),
                strict=True,
            )
        },
    }
    if isinstance(threshold, Mapping):
        result["threshold_mode"] = "per_label"
        result["thresholds"] = {label: float(threshold[label]) for label in LABELS}
    else:
        result["threshold_mode"] = "global"
        result["threshold"] = float(threshold)
    return result


def benchmark_latency(
    predict_fn: Callable[[str], object],
    texts: Sequence[str],
    warmup: int = 5,
) -> dict:
    sample = list(texts[: min(len(texts), 100)])
    if not sample:
        return {"latency_ms_mean": 0.0, "latency_ms_p95": 0.0, "latency_samples": 0}
    for text in sample[:warmup]:
        predict_fn(text)
    timings: list[float] = []
    for text in sample:
        start = time.perf_counter()
        predict_fn(text)
        timings.append((time.perf_counter() - start) * 1000)
    return {
        "latency_ms_mean": float(np.mean(timings)),
        "latency_ms_p95": float(np.percentile(timings, 95)),
        "latency_samples": len(timings),
    }
