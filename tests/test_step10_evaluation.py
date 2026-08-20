from peoplepulse.evaluation.metrics import classification_prf, numeric_grounding, percentile


def test_tool_prf_exact_and_partial():
    exact = classification_prf(["a", "b"], ["b", "a"])
    assert exact["exact_match"] is True
    assert exact["precision"] == 1.0
    assert exact["recall"] == 1.0

    partial = classification_prf(["a", "b"], ["a", "c"])
    assert partial["exact_match"] is False
    assert partial["precision"] == 0.5
    assert partial["recall"] == 0.5


def test_numeric_grounding_supports_percent_conversion():
    result = numeric_grounding(
        "Average Precision은 12.38%다.",
        evidence=[{"average_precision": 0.1238}],
        prompt="모델 성능을 알려줘",
    )
    assert result["unsupported_numeric_claims"] == 0
    assert result["numeric_grounding_rate"] == 1.0


def test_numeric_grounding_flags_unsupported_number():
    result = numeric_grounding(
        "Average Precision은 91%다.",
        evidence=[{"average_precision": 0.1238}],
        prompt="모델 성능을 알려줘",
    )
    assert result["unsupported_numeric_claims"] == 1
    assert result["hallucination_proxy"] is True


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
