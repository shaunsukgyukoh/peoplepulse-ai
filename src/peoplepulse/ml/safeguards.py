from __future__ import annotations

from pathlib import Path


def require_synthetic_training_source(path: str | Path) -> Path:
    """Block employee-level training on non-synthetic files.

    STEP 6 is intentionally a portfolio experiment. Real employee-level employment
    predictions are outside the supported runtime path; production data remains
    department/cohort aggregated in STEP 4/5.
    """
    source = Path(path)
    name = source.name.lower()
    parent_parts = {part.lower() for part in source.parts}
    if "synthetic" not in name and "synthetic" not in parent_parts:
        raise RuntimeError(
            "STEP 6 employee-level model training is synthetic-demo only. "
            "Use a path containing 'synthetic'."
        )
    return source
