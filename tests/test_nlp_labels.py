from peoplepulse.nlp.labels import LABELS, enforce_neutral_exclusivity


def test_labels_are_stable():
    assert LABELS == (
        "satisfied", "neutral", "frustrated", "angry",
        "dissatisfied", "overloaded", "conflict", "disengaged",
    )


def test_neutral_is_suppressed_when_signal_is_strong():
    scores = {label: 0.1 for label in LABELS}
    scores["neutral"] = 0.8
    scores["overloaded"] = 0.9
    out = enforce_neutral_exclusivity(scores, 0.5)
    assert out["neutral"] == 0.0
    assert out["overloaded"] == 0.9
