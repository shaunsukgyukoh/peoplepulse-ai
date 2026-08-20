from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from peoplepulse.config import get_settings
from peoplepulse.monitoring.drift import run_monitoring_cycle
from peoplepulse.monitoring.mlflow_tracking import log_monitoring_snapshot


def _write_failure(root: str, exc: Exception) -> None:
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "error",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "error": f"{type(exc).__name__}: {exc}",
    }
    (path / "latest_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    settings = get_settings()
    print(
        f"PeoplePulse STEP 8 monitoring worker scope={settings.mlops_monitoring_scope} "
        f"interval={settings.mlops_monitoring_interval_seconds}s",
        flush=True,
    )
    while True:
        try:
            summary = run_monitoring_cycle(settings)
            try:
                run_id = log_monitoring_snapshot(
                    summary,
                    tracking_uri=settings.mlflow_tracking_uri,
                    experiment_name=settings.mlflow_monitoring_experiment,
                    artifact_root=settings.mlops_monitoring_artifact_root,
                )
                print(f"[OK] monitoring run logged to MLflow run_id={run_id}", flush=True)
            except Exception as mlflow_exc:
                print(f"[WARN] MLflow logging failed: {mlflow_exc}", flush=True)
            print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        except Exception as exc:
            _write_failure(settings.mlops_monitoring_artifact_root, exc)
            print(f"[ERROR] monitoring cycle failed: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(settings.mlops_monitoring_interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
