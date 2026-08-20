import pandas as pd

from peoplepulse.ml.split import purged_month_split


def test_purged_split_has_disjoint_windows_and_gaps():
    months = pd.period_range("2023-01", periods=36, freq="M")
    frame = pd.DataFrame({"snapshot_month": [month.to_timestamp() for month in months]})
    split = purged_month_split(frame, purge_months=3)
    train = set(split.metadata["train_months"])
    val = set(split.metadata["validation_months"])
    test = set(split.metadata["test_months"])
    gap1 = set(split.metadata["purge_gap_1"])
    gap2 = set(split.metadata["purge_gap_2"])
    assert train.isdisjoint(val | test | gap1 | gap2)
    assert val.isdisjoint(test | gap2)
    assert len(gap1) == 3
    assert len(gap2) == 3
