from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from peoplepulse.activity.report_types import ReportType


@dataclass(frozen=True)
class PrivacyResult:
    frame: pd.DataFrame
    excluded: Counter[str]


class ContentPrivacyFilter:
    """In-memory content filter.

    Raw query text, titles and document names are never returned as features or
    written to PostgreSQL. Sensitive categories are excluded from aggregate
    computation entirely and retained only as batch-level counts.
    """

    def __init__(self, policy_path: str | Path) -> None:
        payload = json.loads(Path(policy_path).read_text(encoding="utf-8"))
        self.version = str(payload["version"])
        self.sensitive_terms: dict[str, tuple[str, ...]] = {
            category: tuple(str(term).lower() for term in terms)
            for category, terms in payload.get("sensitive_terms", {}).items()
        }
        self.compiled = {
            category: tuple(re.compile(re.escape(term), re.IGNORECASE) for term in terms)
            for category, terms in self.sensitive_terms.items()
        }

    def _category_for_text(self, text: str) -> str | None:
        for category, patterns in self.compiled.items():
            if any(pattern.search(text) for pattern in patterns):
                return category
        return None

    def apply(self, report_type: ReportType, frame: pd.DataFrame) -> PrivacyResult:
        if frame.empty:
            return PrivacyResult(frame.copy(), Counter())

        if report_type == ReportType.JOB_SITE_ACCESS:
            text_columns = ["title"]
        elif report_type == ReportType.WEB_SEARCH:
            text_columns = ["query_text", "search_term"]
        else:
            text_columns = ["keyword", "document_name"]

        excluded = Counter()
        keep_mask: list[bool] = []
        for row in frame.to_dict(orient="records"):
            text = " ".join(str(row.get(column) or "") for column in text_columns).lower()
            category = self._category_for_text(text)
            if category:
                excluded[category] += 1
                keep_mask.append(False)
            else:
                keep_mask.append(True)
        return PrivacyResult(frame.loc[keep_mask].reset_index(drop=True), excluded)
