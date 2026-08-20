from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TemporalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    metadata: dict[str, object]


def purged_month_split(
    frame: pd.DataFrame,
    *,
    month_column: str = "snapshot_month",
    purge_months: int = 3,
) -> TemporalSplit:
    """Create train/validation/test windows with horizon-sized purge gaps.

    A 90-day target can use outcomes up to three months after a snapshot. The purge
    gaps prevent training labels from reaching into the next evaluation window.
    """
    result = frame.copy()
    result[month_column] = pd.to_datetime(result[month_column]).dt.to_period("M")
    months = sorted(result[month_column].dropna().unique())
    n = len(months)
    if n < 24:
        raise ValueError("Need at least 24 unique months for purged temporal splitting")

    test_n = max(4, round(n * 0.20))
    val_n = max(4, round(n * 0.15))
    train_n = n - test_n - val_n - 2 * purge_months
    if train_n < 8:
        raise ValueError("Not enough months remain for the training window")

    train_months = months[:train_n]
    gap1 = months[train_n : train_n + purge_months]
    val_start = train_n + purge_months
    val_months = months[val_start : val_start + val_n]
    gap2_start = val_start + val_n
    gap2 = months[gap2_start : gap2_start + purge_months]
    test_months = months[gap2_start + purge_months :]

    train = result[result[month_column].isin(train_months)].copy()
    validation = result[result[month_column].isin(val_months)].copy()
    test = result[result[month_column].isin(test_months)].copy()

    def period_strings(values: list[pd.Period]) -> list[str]:
        return [str(value) for value in values]

    metadata: dict[str, object] = {
        "purge_months": purge_months,
        "train_months": period_strings(train_months),
        "purge_gap_1": period_strings(gap1),
        "validation_months": period_strings(val_months),
        "purge_gap_2": period_strings(gap2),
        "test_months": period_strings(test_months),
        "train_rows": len(train),
        "validation_rows": len(validation),
        "test_rows": len(test),
    }
    return TemporalSplit(train=train, validation=validation, test=test, metadata=metadata)
