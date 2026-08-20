from __future__ import annotations

from collections.abc import Mapping

LABELS: tuple[str, ...] = (
    "satisfied",
    "neutral",
    "frustrated",
    "angry",
    "dissatisfied",
    "overloaded",
    "conflict",
    "disengaged",
)

NON_NEUTRAL_LABELS: tuple[str, ...] = tuple(label for label in LABELS if label != "neutral")
ThresholdSpec = float | Mapping[str, float]


def _threshold_for(label: str, thresholds: ThresholdSpec) -> float:
    if isinstance(thresholds, Mapping):
        return float(thresholds.get(label, 0.5))
    return float(thresholds)


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    return {label: float(max(0.0, min(1.0, scores.get(label, 0.0)))) for label in LABELS}


def derive_active_labels(
    scores: dict[str, float],
    thresholds: ThresholdSpec,
) -> tuple[str, ...]:
    """Convert probabilities into operational labels without changing raw scores.

    Neutral is an exclusive fallback: it is active only when no non-neutral signal
    crosses its own threshold. This keeps stored probabilities auditable while the
    runtime decision uses validation-tuned per-label thresholds.
    """
    normalized = normalize_scores(scores)
    active_non_neutral = tuple(
        label
        for label in NON_NEUTRAL_LABELS
        if normalized[label] >= _threshold_for(label, thresholds)
    )
    if active_non_neutral:
        return active_non_neutral
    if normalized["neutral"] >= _threshold_for("neutral", thresholds):
        return ("neutral",)
    # Always return one fallback state when no signal crosses its threshold.
    return ("neutral",)


def enforce_neutral_exclusivity(
    scores: dict[str, float],
    thresholds: ThresholdSpec,
) -> dict[str, float]:
    """Backward-compatible score shaping helper.

    New runtime code keeps raw probabilities and uses derive_active_labels().
    """
    normalized = normalize_scores(scores)
    active = derive_active_labels(normalized, thresholds)
    if active != ("neutral",):
        normalized["neutral"] = 0.0
    elif normalized["neutral"] < _threshold_for("neutral", thresholds):
        normalized["neutral"] = max(
            normalized["neutral"],
            1.0 - max(normalized[label] for label in NON_NEUTRAL_LABELS),
        )
    return normalized
