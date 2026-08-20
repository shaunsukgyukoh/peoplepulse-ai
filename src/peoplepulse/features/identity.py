from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from peoplepulse.config import Settings
from peoplepulse.security.identifiers import pseudonymize


class IdentityMappingError(ValueError):
    pass


@dataclass(frozen=True)
class IdentityLoadResult:
    mode: str
    input_rows: int
    persisted_rows: int
    mapping_path: str


def _clean(value: object) -> str:
    return str(value or "").strip()


def _normalize_department(value: object) -> str:
    text = _clean(value)
    return text.split(">")[-1].strip()


def _require_columns(frame: pd.DataFrame, required: set[str]) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise IdentityMappingError("Identity mapping is missing columns: " + ", ".join(missing))


def read_identity_mapping(path: str | Path, *, mode: str) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str).fillna("")
    if mode == "aggregate":
        _require_columns(frame, {"slack_user_id", "department"})
        keep = ["slack_user_id", "department"]
    elif mode == "synthetic_demo":
        _require_columns(
            frame,
            {"canonical_employee_key", "slack_user_id", "activity_report_name", "department"},
        )
        keep = [
            "canonical_employee_key",
            "slack_user_id",
            "activity_report_name",
            "department",
        ]
    else:
        raise IdentityMappingError("mode must be aggregate or synthetic_demo")

    frame = frame[keep].copy()
    for column in keep:
        frame[column] = frame[column].map(_clean)
    if (frame[keep] == "").to_numpy().any():
        raise IdentityMappingError("Identity mapping contains blank required values")

    frame["department"] = frame["department"].map(_normalize_department)
    frame = frame.drop_duplicates().reset_index(drop=True)

    if frame["slack_user_id"].duplicated().any():
        raise IdentityMappingError("Each Slack user ID must appear at most once")
    if mode == "synthetic_demo":
        if frame["canonical_employee_key"].duplicated().any():
            raise IdentityMappingError("Each canonical employee key must appear at most once")
        if frame["activity_report_name"].duplicated().any():
            raise IdentityMappingError("Each activity report name must appear at most once")
    return frame


def _aggregate_rows(frame: pd.DataFrame, settings: Settings) -> list[tuple[str, str]]:
    secret = settings.employee_hash_key
    return [
        (
            pseudonymize(row.slack_user_id, secret, namespace="employee"),
            pseudonymize(row.department, secret, namespace="department"),
        )
        for row in frame.itertuples(index=False)
    ]


def _synthetic_rows(frame: pd.DataFrame, settings: Settings) -> list[tuple[str, str, str, str]]:
    secret = settings.employee_hash_key
    return [
        (
            pseudonymize(row.canonical_employee_key, secret, namespace="canonical-employee"),
            pseudonymize(row.slack_user_id, secret, namespace="employee"),
            pseudonymize(row.activity_report_name, secret, namespace="activity-report-name"),
            pseudonymize(row.department, secret, namespace="department"),
        )
        for row in frame.itertuples(index=False)
    ]


def persist_identity_mapping(
    frame: pd.DataFrame,
    *,
    mode: str,
    settings: Settings,
) -> int:
    import psycopg

    settings.validate_activity_runtime()
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            if mode == "aggregate":
                rows = _aggregate_rows(frame, settings)
                cur.execute("DELETE FROM core.slack_department_map")
                cur.executemany(
                    """
                    INSERT INTO core.slack_department_map (
                        slack_employee_id_hash, department_id_hash
                    ) VALUES (%s, %s)
                    """,
                    rows,
                )
            elif mode == "synthetic_demo":
                if settings.app_env == "production":
                    raise IdentityMappingError("synthetic_demo identity mapping is blocked in production")
                rows = _synthetic_rows(frame, settings)
                cur.execute("DELETE FROM core.synthetic_identity_map")
                cur.executemany(
                    """
                    INSERT INTO core.synthetic_identity_map (
                        canonical_employee_id_hash, slack_employee_id_hash,
                        activity_employee_id_hash, department_id_hash
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    rows,
                )
            else:
                raise IdentityMappingError("mode must be aggregate or synthetic_demo")
        conn.commit()
    return len(rows)


def load_identity_mapping(
    path: str | Path,
    *,
    mode: str,
    settings: Settings,
) -> IdentityLoadResult:
    frame = read_identity_mapping(path, mode=mode)
    persisted = persist_identity_mapping(frame, mode=mode, settings=settings)
    return IdentityLoadResult(
        mode=mode,
        input_rows=len(frame),
        persisted_rows=persisted,
        mapping_path=str(path),
    )
