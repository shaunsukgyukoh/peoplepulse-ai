from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np
import pandas as pd

from peoplepulse.ml.features import ALL_MODEL_FEATURES
from peoplepulse.nlp.labels import LABELS


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return float(np.clip(value, low, high))


def _sigmoid(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-value)))


def _hash_id(namespace: str, value: str) -> str:
    return sha256(f"peoplepulse-step6:{namespace}:{value}".encode()).hexdigest()[:32]


@dataclass(frozen=True)
class SyntheticPanelConfig:
    employees: int = 650
    start_month: str = "2023-09"
    months: int = 36
    departments: int = 8
    seed: int = 26082026


def _monthly_features(
    rng: np.random.Generator,
    *,
    base_message_rate: float,
    satisfaction: float,
    strain: float,
    disengagement: float,
    recent_shock: float,
) -> dict[str, float | int]:
    values: dict[str, float | int] = {}

    # Windowed communication activity. Recent windows react more strongly to the shock.
    rate_90 = max(0.05, base_message_rate * (1.0 - 0.30 * disengagement) + rng.normal(0, 0.10))
    rate_30 = max(0.05, rate_90 * (1.0 - 0.12 * disengagement) + rng.normal(0, 0.08))
    rate_7 = max(0.05, rate_30 * (1.0 - 0.18 * disengagement - 0.08 * recent_shock) + rng.normal(0, 0.10))

    for window, rate in ((7, rate_7), (30, rate_30), (90, rate_90)):
        count = max(0, int(round(rate * window + rng.normal(0, max(1.0, rate * 1.5)))))
        values[f"message_count_{window}d"] = count
        values[f"message_rate_{window}d"] = count / window
        values[f"active_days_{window}d"] = min(window, max(0, int(round(window * min(0.85, 0.18 + rate / 7.0)))))

    noise = lambda scale=0.035: float(rng.normal(0, scale))
    neutral_30 = _clip(0.50 - 0.16 * abs(strain - 0.5) + noise())
    signals_30 = {
        "satisfied": _clip(satisfaction + noise()),
        "neutral": neutral_30,
        "frustrated": _clip(0.10 + 0.70 * strain + noise()),
        "angry": _clip(0.03 + 0.38 * strain + 0.12 * recent_shock + noise()),
        "dissatisfied": _clip(0.05 + 0.48 * strain + 0.32 * disengagement + noise()),
        "overloaded": _clip(0.08 + 0.78 * strain + noise()),
        "conflict": _clip(0.04 + 0.27 * strain + 0.15 * recent_shock + noise()),
        "disengaged": _clip(disengagement + noise()),
    }
    for label in LABELS:
        mean30 = signals_30[label]
        direction = -1.0 if label in {"satisfied", "neutral"} else 1.0
        mean7 = _clip(mean30 + direction * 0.18 * recent_shock + noise(0.025))
        mean90 = _clip(mean30 - direction * 0.08 * recent_shock + noise(0.02))
        values[f"{label}_mean_7d"] = mean7
        values[f"{label}_mean_30d"] = mean30
        values[f"{label}_mean_90d"] = mean90
        values[f"{label}_delta_7d_30d"] = mean7 - mean30

    strain_labels = ["frustrated", "angry", "dissatisfied", "overloaded", "conflict", "disengaged"]
    for window in (7, 30, 90):
        values[f"work_strain_mean_{window}d"] = float(
            np.mean([values[f"{label}_mean_{window}d"] for label in strain_labels])
        )
    values["message_rate_delta_7d_30d"] = float(values["message_rate_7d"] - values["message_rate_30d"])
    values["work_strain_delta_7d_30d"] = float(
        values["work_strain_mean_7d"] - values["work_strain_mean_30d"]
    )

    # Synthetic-only month-end activity features. Direct intent proxies are kept for
    # ablation experiments but excluded from the default privacy_safe feature set.
    intent = _clip(0.55 * disengagement + 0.35 * strain + 0.30 * recent_shock + rng.normal(0, 0.08))
    job_events = int(rng.poisson(max(0.05, 0.5 + 8.0 * intent**2)))
    search_events = int(rng.poisson(max(0.05, 1.2 + 7.0 * intent)))
    doc_events = int(rng.poisson(max(0.1, 6.0 + 4.0 * strain + 1.0 * recent_shock)))
    values.update(
        {
            "job_site_events": job_events,
            "job_site_seconds": float(job_events * max(0.0, rng.normal(360, 110))),
            "job_site_active_days": min(31, max(0, int(round(job_events * 0.65)))),
            "web_search_events": search_events,
            "web_search_active_days": min(31, max(0, int(round(search_events * 0.55)))),
            "document_usage_events": doc_events,
            "document_active_days": min(31, max(1, int(round(doc_events * 0.55)))),
            "document_create_events": max(0, int(round(doc_events * 0.18 + rng.normal(0, 0.7)))),
            "document_modify_events": max(0, int(round(doc_events * 0.45 + rng.normal(0, 0.8)))),
            "document_view_events": max(0, int(round(doc_events * 0.37 + rng.normal(0, 0.8)))),
            "after_hours_search_ratio": _clip(0.08 + 0.35 * intent + rng.normal(0, 0.05)),
            "after_hours_document_ratio": _clip(0.07 + 0.30 * strain + rng.normal(0, 0.05)),
            "weekend_search_ratio": _clip(0.05 + 0.24 * intent + rng.normal(0, 0.04)),
            "weekend_document_ratio": _clip(0.04 + 0.18 * strain + rng.normal(0, 0.04)),
        }
    )
    return values


def generate_synthetic_attrition_panel(
    config: SyntheticPanelConfig = SyntheticPanelConfig(),
) -> pd.DataFrame:
    rng = np.random.default_rng(config.seed)
    months = pd.period_range(config.start_month, periods=config.months, freq="M")
    records: list[dict[str, object]] = []
    event_month_by_employee: dict[str, pd.Period | None] = {}

    for employee_idx in range(config.employees):
        employee_key = f"synthetic-employee-{employee_idx:04d}"
        employee_hash = _hash_id("employee", employee_key)
        department_idx = int(rng.integers(0, config.departments))
        department_hash = _hash_id("department", f"synthetic-dept-{department_idx:02d}")
        base_message_rate = float(rng.lognormal(mean=0.75, sigma=0.40))
        satisfaction = _clip(rng.normal(0.66, 0.12))
        strain = _clip(rng.normal(0.30, 0.11))
        disengagement = _clip(rng.normal(0.18, 0.09))
        tenure_months = int(rng.integers(3, 90))
        departure_period: pd.Period | None = None

        employee_rows: list[dict[str, object]] = []
        for month_idx, snapshot in enumerate(months):
            if departure_period is not None and snapshot >= departure_period:
                break

            seasonal = 0.06 * np.sin((month_idx + department_idx) / 3.5)
            shock = float(max(0.0, rng.normal(0.0, 0.16))) if rng.random() < 0.14 else 0.0
            strain = _clip(0.78 * strain + 0.10 + seasonal + shock + rng.normal(0, 0.045))
            disengagement = _clip(
                0.82 * disengagement + 0.12 * strain - 0.07 * satisfaction + 0.20 * shock + rng.normal(0, 0.035)
            )
            satisfaction = _clip(
                0.80 * satisfaction + 0.13 - 0.16 * strain - 0.09 * disengagement + rng.normal(0, 0.035)
            )

            features = _monthly_features(
                rng,
                base_message_rate=base_message_rate,
                satisfaction=satisfaction,
                strain=strain,
                disengagement=disengagement,
                recent_shock=shock,
            )
            row: dict[str, object] = {
                "canonical_employee_id_hash": employee_hash,
                "department_id_hash": department_hash,
                "snapshot_month": snapshot.to_timestamp().date(),
                **features,
                "has_activity_data": True,
                "has_slack_data": True,
            }
            employee_rows.append(row)

            # A stochastic event can happen after this snapshot. No target is written here;
            # targets are derived only after the event timeline is complete.
            if month_idx >= 5:
                logit = (
                    -5.15
                    + 2.25 * strain
                    + 2.10 * disengagement
                    - 1.15 * satisfaction
                    + 0.85 * max(0.0, float(features["work_strain_delta_7d_30d"]))
                    + 0.025 * min(48, tenure_months) / 12.0
                )
                hazard = min(0.22, _sigmoid(logit))
                if rng.random() < hazard and month_idx < len(months) - 1:
                    departure_period = months[month_idx + 1]
            tenure_months += 1

        event_month_by_employee[employee_hash] = departure_period
        records.extend(employee_rows)

    frame = pd.DataFrame(records)
    if frame.empty:
        return frame

    event_lookup = event_month_by_employee
    for horizon, months_ahead in ((30, 1), (60, 2), (90, 3)):
        targets: list[int] = []
        for row in frame.itertuples(index=False):
            snapshot = pd.Period(pd.Timestamp(row.snapshot_month), freq="M")
            event = event_lookup[str(row.canonical_employee_id_hash)]
            if event is None:
                targets.append(0)
                continue
            distance = int(event.ordinal - snapshot.ordinal)
            targets.append(int(1 <= distance <= months_ahead))
        frame[f"attrition_{horizon}d"] = targets

    missing = [column for column in ALL_MODEL_FEATURES if column not in frame.columns]
    if missing:
        raise RuntimeError(f"Synthetic generator missing STEP 5 features: {missing}")
    return frame
