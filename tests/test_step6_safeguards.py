from pathlib import Path

import pytest

from peoplepulse.ml.safeguards import require_synthetic_training_source


def test_training_source_blocks_non_synthetic_path():
    with pytest.raises(RuntimeError):
        require_synthetic_training_source(Path("data/real/employees.csv"))


def test_training_source_allows_synthetic_path():
    path = Path("data/synthetic/ml/panel.csv")
    assert require_synthetic_training_source(path) == path
