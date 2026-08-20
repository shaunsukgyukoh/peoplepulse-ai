from peoplepulse.nlp.labels import derive_active_labels


def test_per_label_thresholds_activate_multiple_signals():
    thresholds = {
        "satisfied": 0.5,
        "neutral": 0.6,
        "frustrated": 0.4,
        "angry": 0.7,
        "dissatisfied": 0.5,
        "overloaded": 0.45,
        "conflict": 0.6,
        "disengaged": 0.5,
    }
    scores = {
        "satisfied": 0.1,
        "neutral": 0.8,
        "frustrated": 0.72,
        "angry": 0.2,
        "dissatisfied": 0.3,
        "overloaded": 0.71,
        "conflict": 0.1,
        "disengaged": 0.2,
    }
    assert derive_active_labels(scores, thresholds) == ("frustrated", "overloaded")


def test_neutral_is_fallback_when_no_signal_crosses_threshold():
    thresholds = {label: 0.7 for label in (
        "satisfied", "neutral", "frustrated", "angry", "dissatisfied",
        "overloaded", "conflict", "disengaged"
    )}
    scores = {label: 0.1 for label in thresholds}
    assert derive_active_labels(scores, thresholds) == ("neutral",)
