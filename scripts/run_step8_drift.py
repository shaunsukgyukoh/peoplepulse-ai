from __future__ import annotations

import argparse
import json

from peoplepulse.config import get_settings
from peoplepulse.monitoring.drift import run_monitoring_cycle
from peoplepulse.monitoring.mlflow_tracking import log_monitoring_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one PeoplePulse STEP 8 Evidently monitoring cycle")
    parser.add_argument("--scope", choices=["aggregate", "synthetic_demo"], default=None)
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    summary = run_monitoring_cycle(settings, scope=args.scope)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.no_mlflow:
        try:
            run_id = log_monitoring_snapshot(
                summary,
                tracking_uri=settings.mlflow_tracking_uri,
                experiment_name=settings.mlflow_monitoring_experiment,
                artifact_root=settings.mlops_monitoring_artifact_root,
            )
            print(f"[OK] MLflow monitoring run_id={run_id}")
        except Exception as exc:
            print(f"[WARN] MLflow logging skipped/failed: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
