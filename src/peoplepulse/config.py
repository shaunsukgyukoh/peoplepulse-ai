from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"

    postgres_db: str = "peoplepulse"
    postgres_user: str = "peoplepulse"
    postgres_password: str = "change-me-local-only"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = "change-me-local-only"
    redis_db: int = 0
    redis_stream_slack_events: str = "peoplepulse:slack-events"
    redis_stream_nlp_results: str = "peoplepulse:nlp-results"
    redis_stream_slack_maxlen: int = 10_000
    slack_event_dedup_ttl_seconds: int = 604_800

    nlp_consumer_group: str = "peoplepulse:nlp-workers"
    nlp_batch_size: int = 8
    nlp_block_ms: int = 5_000
    nlp_redis_socket_timeout_seconds: float = 15.0
    nlp_pending_min_idle_ms: int = 60_000
    nlp_recovery_interval_seconds: int = 30
    redis_stream_nlp_maxlen: int = 50_000
    nlp_backend: str = "transformer"
    nlp_model_path: str = "/models/selected"
    nlp_baseline_model_path: str = "/models/tfidf-logreg/model.joblib"
    nlp_threshold: float = 0.5
    nlp_device: str = "auto"

    slack_bot_token: str = ""
    slack_app_token: str = ""
    employee_hash_key: str = "replace-with-a-long-random-secret"

    activity_domain_policy_path: str = "configs/activity_domain_policy.json"  # legacy STEP 4.0
    activity_content_policy_path: str = "configs/activity_content_policy.json"
    activity_admin_token: str = "replace-with-a-long-random-admin-token"
    activity_internal_domains: str = ""  # legacy STEP 4.0
    activity_max_upload_bytes: int = 20 * 1024 * 1024
    activity_workday_start_hour: int = 9
    activity_workday_end_hour: int = 18
    activity_privacy_mode: str = "aggregate"
    activity_min_cohort_size: int = 5
    activity_demo_filename_prefix: str = "Synthetic_"

    dashboard_step6_artifact_root: str = "artifacts/ml/step6"
    dashboard_step6_reference_metrics_path: str = (
        "docs/experiment-results/step6_reference_metrics.json"
    )
    dashboard_nlp_metrics_path: str = (
        "docs/experiment-results/nlp_model_comparison_step3_1.json"
    )
    dashboard_shap_path: str = (
        "artifacts/ml/step6/privacy_safe/shap/shap_feature_importance.csv"
    )
    dashboard_stream_interval_seconds: float = 2.0
    dashboard_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def dashboard_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.dashboard_allowed_origins.split(",") if origin.strip()]

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def validate_nlp_runtime(self) -> None:
        errors: list[str] = []
        if self.nlp_backend not in {"baseline", "transformer"}:
            errors.append("NLP_BACKEND must be baseline or transformer")
        if not 0.0 < self.nlp_threshold < 1.0:
            errors.append("NLP_THRESHOLD must be between 0 and 1")
        if self.nlp_batch_size < 1:
            errors.append("NLP_BATCH_SIZE must be >= 1")
        if self.nlp_redis_socket_timeout_seconds <= (self.nlp_block_ms / 1000):
            errors.append(
                "NLP_REDIS_SOCKET_TIMEOUT_SECONDS must be greater than NLP_BLOCK_MS / 1000"
            )
        if errors:
            raise RuntimeError("Invalid NLP runtime configuration:\n- " + "\n- ".join(errors))

    def validate_activity_runtime(self) -> None:
        errors: list[str] = []
        if self.employee_hash_key in {"", "replace-with-a-long-random-secret"}:
            errors.append("EMPLOYEE_HASH_KEY must be replaced with a long random secret")
        if not 0 <= self.activity_workday_start_hour <= 23:
            errors.append("ACTIVITY_WORKDAY_START_HOUR must be between 0 and 23")
        if not 1 <= self.activity_workday_end_hour <= 24:
            errors.append("ACTIVITY_WORKDAY_END_HOUR must be between 1 and 24")
        if self.activity_workday_start_hour >= self.activity_workday_end_hour:
            errors.append("ACTIVITY_WORKDAY_START_HOUR must be earlier than ACTIVITY_WORKDAY_END_HOUR")
        if self.activity_max_upload_bytes < 1024:
            errors.append("ACTIVITY_MAX_UPLOAD_BYTES must be >= 1024")
        if self.activity_privacy_mode not in {"aggregate", "synthetic_demo"}:
            errors.append("ACTIVITY_PRIVACY_MODE must be aggregate or synthetic_demo")
        if self.activity_privacy_mode == "synthetic_demo" and self.app_env == "production":
            errors.append(
                "ACTIVITY_PRIVACY_MODE=synthetic_demo is blocked when APP_ENV=production"
            )
        if self.activity_min_cohort_size < 2:
            errors.append("ACTIVITY_MIN_COHORT_SIZE must be >= 2")
        if not self.activity_demo_filename_prefix:
            errors.append("ACTIVITY_DEMO_FILENAME_PREFIX must not be blank")
        if errors:
            raise RuntimeError("Invalid activity runtime configuration:\n- " + "\n- ".join(errors))

    def validate_activity_api_runtime(self) -> None:
        self.validate_activity_runtime()
        if self.activity_admin_token in {"", "replace-with-a-long-random-admin-token"}:
            raise RuntimeError(
                "Invalid activity API runtime configuration:\n- "
                "ACTIVITY_ADMIN_TOKEN must be replaced with a long random secret"
            )

    def validate_slack_runtime(self) -> None:
        errors: list[str] = []
        if not self.slack_bot_token.startswith("xoxb-"):
            errors.append("SLACK_BOT_TOKEN must be a Bot User OAuth token starting with xoxb-")
        if not self.slack_app_token.startswith("xapp-"):
            errors.append("SLACK_APP_TOKEN must be an app-level token starting with xapp-")
        if self.employee_hash_key in {"", "replace-with-a-long-random-secret"}:
            errors.append("EMPLOYEE_HASH_KEY must be replaced with a long random secret")
        if errors:
            raise RuntimeError("Invalid Slack runtime configuration:\n- " + "\n- ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
