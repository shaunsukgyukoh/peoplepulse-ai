from __future__ import annotations

import math
import re
from collections.abc import Iterable
from statistics import mean
from typing import Any

_NUM_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?%?")
_ORDERED_LIST_RE = re.compile(r"(?m)^\s*\d+[.)]\s+")


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    weight = pos - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def classification_prf(expected: Iterable[str], actual: Iterable[str]) -> dict[str, float | bool]:
    expected_set = set(expected)
    actual_set = set(actual)
    tp = len(expected_set & actual_set)
    precision = tp / len(actual_set) if actual_set else (1.0 if not expected_set else 0.0)
    recall = tp / len(expected_set) if expected_set else (1.0 if not actual_set else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "exact_match": expected_set == actual_set,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _walk_numbers(value: Any) -> list[float]:
    result: list[float] = []
    if isinstance(value, bool) or value is None:
        return result
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            result.append(float(value))
        return result
    if isinstance(value, dict):
        for key, item in value.items():
            result.extend(_walk_numbers(key))
            result.extend(_walk_numbers(item))
        return result
    if isinstance(value, (list, tuple, set)):
        for item in value:
            result.extend(_walk_numbers(item))
        return result
    if isinstance(value, str):
        result.extend(extract_numbers(value))
    return result


def extract_numbers(text: str) -> list[float]:
    # Markdown numbered lists are formatting, not factual numeric claims.
    scrubbed = _ORDERED_LIST_RE.sub("", text or "")
    numbers: list[float] = []
    for match in _NUM_RE.finditer(scrubbed):
        token = match.group(0)
        is_percent = token.endswith("%")
        raw = token[:-1] if is_percent else token
        try:
            value = float(raw)
        except ValueError:
            continue
        numbers.append(value / 100.0 if is_percent else value)
    return numbers


def _is_supported(value: float, candidates: list[float]) -> bool:
    for candidate in candidates:
        tolerance = max(1e-6, abs(candidate) * 0.005)
        if abs(value - candidate) <= tolerance:
            return True
    return False


def numeric_grounding(answer: str, *, evidence: Any, prompt: str) -> dict[str, Any]:
    claims = extract_numbers(answer)
    candidates = _walk_numbers(evidence) + extract_numbers(prompt)
    unsupported = [value for value in claims if not _is_supported(value, candidates)]
    supported_count = len(claims) - len(unsupported)
    return {
        "numeric_claims": len(claims),
        "supported_numeric_claims": supported_count,
        "unsupported_numeric_claims": len(unsupported),
        "unsupported_values": unsupported,
        "numeric_grounding_rate": supported_count / len(claims) if claims else 1.0,
        "hallucination_proxy": bool(unsupported),
    }


def aggregate_latency(values_ms: list[float]) -> dict[str, float | None]:
    return {
        "count": len(values_ms),
        "mean_ms": mean(values_ms) if values_ms else None,
        "p50_ms": percentile(values_ms, 0.50),
        "p95_ms": percentile(values_ms, 0.95),
        "p99_ms": percentile(values_ms, 0.99),
        "max_ms": max(values_ms) if values_ms else None,
    }
