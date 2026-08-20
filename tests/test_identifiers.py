from peoplepulse.security.identifiers import pseudonymize


def test_pseudonymize_is_stable_and_namespaced() -> None:
    key = "a-long-test-secret"
    one = pseudonymize("U123", key, namespace="employee")
    two = pseudonymize("U123", key, namespace="employee")
    channel = pseudonymize("U123", key, namespace="channel")
    assert one == two
    assert one != channel
    assert "U123" not in one
    assert len(one) == 32
