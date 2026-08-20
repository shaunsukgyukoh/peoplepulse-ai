from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

import psycopg

from peoplepulse.config import get_settings
from peoplepulse.nlp.labels import LABELS
from peoplepulse.security.identifiers import pseudonymize

EMPLOYEES = {
    "UDEMO001": "stable-positive",
    "UDEMO002": "rising-workload",
    "UDEMO003": "mixed-disengagement",
}


def bounded(value: float) -> float:
    return max(0.01, min(0.99, value))


def scores_for(profile: str, day_index: int, rng: random.Random) -> dict[str, float]:
    progress = day_index / 89
    noise = lambda scale=0.04: rng.uniform(-scale, scale)
    if profile == "stable-positive":
        values = {
            "satisfied": 0.78 + noise(),
            "neutral": 0.30 + noise(),
            "frustrated": 0.16 + noise(),
            "angry": 0.08 + noise(0.02),
            "dissatisfied": 0.12 + noise(),
            "overloaded": 0.20 + noise(),
            "conflict": 0.10 + noise(0.03),
            "disengaged": 0.12 + noise(),
        }
    elif profile == "rising-workload":
        values = {
            "satisfied": 0.62 - 0.30 * progress + noise(),
            "neutral": 0.32 + noise(),
            "frustrated": 0.22 + 0.48 * progress + noise(),
            "angry": 0.10 + 0.18 * progress + noise(0.03),
            "dissatisfied": 0.18 + 0.36 * progress + noise(),
            "overloaded": 0.25 + 0.55 * progress + noise(),
            "conflict": 0.12 + 0.15 * progress + noise(0.03),
            "disengaged": 0.14 + 0.24 * progress + noise(),
        }
    else:
        wave = (math.sin(day_index / 8) + 1) / 2
        values = {
            "satisfied": 0.45 - 0.18 * progress + noise(),
            "neutral": 0.38 + noise(),
            "frustrated": 0.30 + 0.12 * wave + noise(),
            "angry": 0.12 + noise(0.03),
            "dissatisfied": 0.28 + 0.15 * progress + noise(),
            "overloaded": 0.34 + 0.12 * wave + noise(),
            "conflict": 0.14 + noise(0.03),
            "disengaged": 0.30 + 0.32 * progress + noise(),
        }
    return {key: bounded(value) for key, value in values.items()}


def main() -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise RuntimeError("Synthetic Slack seeding is blocked in production")
    rng = random.Random(42)
    anchor = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    start = anchor - timedelta(days=89)
    rows: list[tuple[object, ...]] = []
    for user_id, profile in EMPLOYEES.items():
        employee_hash = pseudonymize(user_id, settings.employee_hash_key, namespace="employee")
        for day_index in range(90):
            day = start + timedelta(days=day_index)
            # Deterministic activity density: 0-3 derived messages per day.
            base = 2 if profile != "mixed-disengagement" else (2 if day_index < 55 else 1)
            count = max(0, base + rng.choice([-1, 0, 0, 1]))
            for msg_idx in range(count):
                scores = scores_for(profile, day_index, rng)
                active = [label for label in LABELS if scores[label] >= 0.5]
                ts = day + timedelta(hours=msg_idx * 2)
                rows.append(
                    (
                        f"step5-demo-{user_id}-{day_index:03d}-{msg_idx}",
                        employee_hash,
                        pseudonymize("CDEMO", settings.employee_hash_key, namespace="channel"),
                        "channel",
                        ts,
                        ts,
                        "synthetic-seed",
                        "step5-demo-v1",
                        0.5,
                        1.0,
                        "{}",
                        active,
                        "synthetic",
                        *[scores[label] for label in LABELS],
                    )
                )

    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM features.message_nlp_signal WHERE event_id LIKE 'step5-demo-%'")
            cur.executemany(
                """
                INSERT INTO features.message_nlp_signal (
                    event_id, employee_id_hash, channel_id_hash, channel_type,
                    message_ts, received_at, model_name, model_version,
                    threshold, inference_ms, thresholds, active_labels, model_device,
                    satisfied, neutral, frustrated, angry, dissatisfied, overloaded,
                    conflict, disengaged
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s
                )
                """,
                rows,
            )
        conn.commit()
    print(f"[OK] seeded synthetic derived Slack signals rows={len(rows)}")


if __name__ == "__main__":
    main()
