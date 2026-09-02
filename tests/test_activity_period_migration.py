from pathlib import Path


def test_period_migration_is_in_runtime_migration_paths() -> None:
    migration = Path("infra/postgres/migrations/009_activity_report_periods.sql").read_text(
        encoding="utf-8"
    )
    production_runner = Path("scripts/apply_production_main_migration.py").read_text(
        encoding="utf-8"
    )
    all_runner = Path("scripts/apply_all_migrations.py").read_text(encoding="utf-8")

    assert "period_start" in migration
    assert "period_end" in migration
    assert production_runner.index("005_step4_actual_report_set.sql") < production_runner.index(
        "009_activity_report_periods.sql"
    )
    assert "009_activity_report_periods.sql" in production_runner
    assert "009_activity_report_periods.sql" in all_runner
