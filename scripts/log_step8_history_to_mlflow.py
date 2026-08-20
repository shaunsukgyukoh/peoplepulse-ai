from __future__ import annotations

from pathlib import Path

from peoplepulse.config import get_settings
from peoplepulse.monitoring.mlflow_tracking import import_nlp_benchmark, import_step6_experiments


def main() -> int:
    settings = get_settings()

    # Derive the STEP 6 artifact root from the configured predictions path so
    # the same script works both locally (artifacts/...) and inside Docker
    # (/artifacts/...).
    step6_artifact_root = Path(settings.mlops_predictions_path).parent.parent

    step6 = import_step6_experiments(
        tracking_uri=settings.mlflow_tracking_uri,
        artifact_root=step6_artifact_root,
    )
    nlp = import_nlp_benchmark(tracking_uri=settings.mlflow_tracking_uri)
    print(
        "[OK] MLflow import "
        f"step6_runs={len(step6)} nlp_runs={len(nlp)} "
        f"step6_artifact_root={step6_artifact_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
