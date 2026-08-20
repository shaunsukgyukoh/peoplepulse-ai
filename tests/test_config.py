import pytest

from peoplepulse.config import Settings


def test_default_stream_names() -> None:
    settings = Settings(_env_file=None)
    assert settings.redis_stream_slack_events == "peoplepulse:slack-events"
    assert settings.redis_stream_nlp_results == "peoplepulse:nlp-results"


def test_postgres_dsn_contains_database() -> None:
    settings = Settings(_env_file=None)
    assert settings.postgres_dsn.endswith("/peoplepulse")


def test_nlp_redis_socket_timeout_exceeds_block_window() -> None:
    settings = Settings(_env_file=None)
    assert settings.nlp_redis_socket_timeout_seconds > settings.nlp_block_ms / 1000


def test_invalid_nlp_redis_timeout_is_rejected() -> None:
    settings = Settings(
        _env_file=None,
        nlp_block_ms=5000,
        nlp_redis_socket_timeout_seconds=5.0,
    )
    try:
        settings.validate_nlp_runtime()
    except RuntimeError as exc:
        assert "NLP_REDIS_SOCKET_TIMEOUT_SECONDS" in str(exc)
    else:
        raise AssertionError("Expected invalid NLP Redis socket timeout to be rejected")


def test_activity_runtime_rejects_placeholders() -> None:
    settings = Settings()
    with pytest.raises(RuntimeError):
        settings.validate_activity_runtime()


def test_activity_runtime_accepts_secure_local_values() -> None:
    settings = Settings(employee_hash_key="employee-hmac-secret-for-tests")
    settings.validate_activity_runtime()


def test_activity_api_runtime_requires_admin_secret() -> None:
    settings = Settings(employee_hash_key="employee-hmac-secret-for-tests")
    with pytest.raises(RuntimeError):
        settings.validate_activity_api_runtime()
    settings = Settings(
        employee_hash_key="employee-hmac-secret-for-tests",
        activity_admin_token="admin-secret-for-tests",
    )
    settings.validate_activity_api_runtime()
