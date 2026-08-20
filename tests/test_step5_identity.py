from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from peoplepulse.features.identity import IdentityMappingError, read_identity_mapping


def test_synthetic_identity_mapping_reads_expected_columns(tmp_path: Path) -> None:
    path = tmp_path / "map.csv"
    pd.DataFrame(
        [
            {
                "canonical_employee_key": "demo-1",
                "slack_user_id": "U001",
                "activity_report_name": "홍길동",
                "department": "(주)샘플 > 개발팀",
            }
        ]
    ).to_csv(path, index=False)
    frame = read_identity_mapping(path, mode="synthetic_demo")
    assert frame.loc[0, "department"] == "개발팀"
    assert frame.loc[0, "slack_user_id"] == "U001"


def test_identity_mapping_rejects_duplicate_slack_ids(tmp_path: Path) -> None:
    path = tmp_path / "map.csv"
    pd.DataFrame(
        [
            {"slack_user_id": "U001", "department": "개발팀"},
            {"slack_user_id": "U001", "department": "전략팀"},
        ]
    ).to_csv(path, index=False)
    with pytest.raises(IdentityMappingError):
        read_identity_mapping(path, mode="aggregate")
