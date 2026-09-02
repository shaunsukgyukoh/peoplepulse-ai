from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from peoplepulse.security.identifiers import pseudonymize

_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
_POLITE_ENDING_PATTERN = re.compile(r"(?:요|니다)[.!?]*$")
_STOP_TOKENS = {
    "가능한",
    "내용이",
    "다시",
    "다음",
    "먼저",
    "마지막으로",
    "부탁드립니다",
    "오늘입니다",
    "있을까요",
    "추가로",
    "확인",
}


def load_synthetic_personas(path: str | Path, *, secret: str) -> list[dict[str, str]]:
    """Load the committed fictional identity catalog and derive its join hashes."""
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "canonical_employee_key",
            "activity_report_name",
            "department",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("synthetic identity catalog is missing required columns")
        rows = []
        for row in reader:
            canonical_key = (row.get("canonical_employee_key") or "").strip()
            display_name = (row.get("activity_report_name") or "").strip()
            department = (row.get("department") or "").strip()
            if not canonical_key or not display_name or not department:
                raise ValueError("synthetic identity catalog contains blank required values")
            rows.append(
                {
                    "canonical_employee_key": canonical_key,
                    "employee_name": display_name,
                    "department": department,
                    "activity_employee_id_hash": pseudonymize(
                        display_name,
                        secret,
                        namespace="activity-report-name",
                    ),
                }
            )
    return rows


def empty_text_statistics() -> dict[str, Any]:
    return {
        "period_start": None,
        "period_end": None,
        "message_count": 0,
        "non_whitespace_character_count": 0,
        "token_count": 0,
        "average_characters_per_message": 0.0,
        "question_mark_count": 0,
        "exclamation_mark_count": 0,
        "polite_ending_message_count": 0,
        "polite_ending_message_ratio": 0.0,
        "top_terms": [],
    }


def load_structural_text_statistics(path: str | Path) -> dict[str, dict[str, Any]]:
    """Compute literal structure counts without sentiment, tone, or state inference."""
    messages: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"canonical_employee_key", "occurred_at", "text"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("synthetic message fixture is missing required columns")
        for row in reader:
            canonical_key = (row.get("canonical_employee_key") or "").strip()
            text = (row.get("text") or "").strip()
            occurred_at = datetime.fromisoformat((row.get("occurred_at") or "").strip())
            if not canonical_key or not text:
                raise ValueError("synthetic message fixture contains blank required values")
            messages[canonical_key].append((occurred_at, text))

    result: dict[str, dict[str, Any]] = {}
    for canonical_key, rows in messages.items():
        stats = empty_text_statistics()
        rows.sort(key=lambda item: item[0])
        texts = [text for _, text in rows]
        tokens = [token for text in texts for token in _TOKEN_PATTERN.findall(text)]
        term_counts = Counter(
            token
            for token in tokens
            if len(token) >= 2 and token not in _STOP_TOKENS and not token.isdigit()
        )
        message_count = len(texts)
        character_count = sum(len(re.sub(r"\s+", "", text)) for text in texts)
        polite_count = sum(bool(_POLITE_ENDING_PATTERN.search(text)) for text in texts)
        stats.update(
            {
                "period_start": rows[0][0].date().isoformat(),
                "period_end": rows[-1][0].date().isoformat(),
                "message_count": message_count,
                "non_whitespace_character_count": character_count,
                "token_count": len(tokens),
                "average_characters_per_message": round(character_count / message_count, 2),
                "question_mark_count": sum(text.count("?") for text in texts),
                "exclamation_mark_count": sum(text.count("!") for text in texts),
                "polite_ending_message_count": polite_count,
                "polite_ending_message_ratio": round(polite_count / message_count, 4),
                "top_terms": [
                    {"term": term, "count": count}
                    for term, count in term_counts.most_common(6)
                ],
            }
        )
        result[canonical_key] = stats
    return result
