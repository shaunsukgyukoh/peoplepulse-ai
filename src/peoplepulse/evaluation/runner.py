from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from peoplepulse.agent.policy import evaluate_request
from peoplepulse.evaluation.metrics import aggregate_latency, classification_prf, numeric_grounding

DEFAULT_GATES = {
    "policy_accuracy_min": 1.0,
    "tool_exact_match_min": 0.80,
    "tool_recall_min": 0.90,
    "structured_citation_rate_min": 0.95,
    "citation_text_rate_min": 0.80,
    "hallucination_proxy_case_rate_max": 0.10,
    "allowed_latency_p95_ms_max": 10000.0,
}


@dataclass(frozen=True)
class EvalCase:
    id: str
    scope: str
    message: str
    expected_blocked: bool
    expected_tools: tuple[str, ...]
    expected_sources: tuple[str, ...]
    tags: tuple[str, ...]

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "EvalCase":
        return cls(
            id=str(row["id"]),
            scope=str(row.get("scope", "aggregate")),
            message=str(row["message"]),
            expected_blocked=bool(row.get("expected_blocked", False)),
            expected_tools=tuple(row.get("expected_tools", [])),
            expected_sources=tuple(row.get("expected_sources", [])),
            tags=tuple(row.get("tags", [])),
        )


def load_cases(path: str | Path) -> list[EvalCase]:
    rows: list[EvalCase] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        rows.append(EvalCase.from_dict(json.loads(line)))
    return rows


def _source_matches(expected: tuple[str, ...], actual: list[str]) -> dict[str, float | bool]:
    matched: set[str] = set()
    for item in expected:
        if any(item == source or item in source for source in actual):
            matched.add(item)
    recall = len(matched) / len(expected) if expected else 1.0
    return {"recall": recall, "exact_or_contains_all": recall == 1.0}


def _citation_in_text(answer: str, sources: list[str]) -> bool:
    lower = answer.lower()
    return any(source.lower() in lower for source in sources if source)


def evaluate_cases(cases: list[EvalCase], *, policy_only: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    agent_latencies: list[float] = []
    policy_latencies: list[float] = []

    for index, case in enumerate(cases):
        started = time.perf_counter()
        decision = evaluate_request(case.message, scope=case.scope)
        policy_ms = (time.perf_counter() - started) * 1000
        policy_latencies.append(policy_ms)
        policy_ok = (not decision.allowed) == case.expected_blocked

        record: dict[str, Any] = {
            "id": case.id,
            "scope": case.scope,
            "message": case.message,
            "tags": list(case.tags),
            "expected_blocked": case.expected_blocked,
            "policy_allowed": decision.allowed,
            "policy_ok": policy_ok,
            "policy_reason": decision.reason,
            "policy_latency_ms": round(policy_ms, 3),
        }

        if policy_only or case.expected_blocked or not decision.allowed:
            record["task_success"] = policy_ok
            results.append(record)
            continue

        started = time.perf_counter()
        from peoplepulse.agent.service import evaluation_chat

        response = evaluation_chat(
            case.message,
            scope=case.scope,
            thread_id=f"step10-eval-{case.id}-{index}",
        )
        agent_ms = (time.perf_counter() - started) * 1000
        agent_latencies.append(agent_ms)

        actual_tools = list(response.get("tool_calls", []))
        sources = list(response.get("sources", []))
        answer = str(response.get("answer", ""))
        evidence = response.get("evidence", [])

        tool_metrics = classification_prf(case.expected_tools, actual_tools)
        source_metrics = _source_matches(case.expected_sources, sources)
        grounding = numeric_grounding(answer, evidence=evidence, prompt=case.message)
        structured_citation = bool(sources)
        text_citation = _citation_in_text(answer, sources) if sources else False

        task_success = bool(answer.strip()) and bool(tool_metrics["recall"] == 1.0) and bool(source_metrics["recall"] == 1.0)

        record.update(
            {
                "answer": answer,
                "blocked": bool(response.get("blocked", False)),
                "model": response.get("model"),
                "agent_latency_ms": round(agent_ms, 3),
                "expected_tools": list(case.expected_tools),
                "actual_tools": actual_tools,
                "tool_metrics": tool_metrics,
                "expected_sources": list(case.expected_sources),
                "sources": sources,
                "source_recall": source_metrics["recall"],
                "structured_citation": structured_citation,
                "citation_in_answer_text": text_citation,
                "grounding": grounding,
                "task_success": task_success,
            }
        )
        results.append(record)

    policy_accuracy = sum(1 for row in results if row["policy_ok"]) / len(results) if results else 0.0
    allowed_rows = [row for row in results if "agent_latency_ms" in row]
    blocked_rows = [row for row in results if row["expected_blocked"]]

    tool_exact = (
        sum(1 for row in allowed_rows if row["tool_metrics"]["exact_match"]) / len(allowed_rows)
        if allowed_rows else None
    )
    tool_recall = (
        sum(float(row["tool_metrics"]["recall"]) for row in allowed_rows) / len(allowed_rows)
        if allowed_rows else None
    )
    citation_rate = (
        sum(1 for row in allowed_rows if row["structured_citation"]) / len(allowed_rows)
        if allowed_rows else None
    )
    citation_text_rate = (
        sum(1 for row in allowed_rows if row["citation_in_answer_text"]) / len(allowed_rows)
        if allowed_rows else None
    )
    hallucination_proxy_case_rate = (
        sum(1 for row in allowed_rows if row["grounding"]["hallucination_proxy"]) / len(allowed_rows)
        if allowed_rows else None
    )
    numeric_claims = sum(int(row["grounding"]["numeric_claims"]) for row in allowed_rows)
    unsupported_numeric = sum(int(row["grounding"]["unsupported_numeric_claims"]) for row in allowed_rows)
    numeric_grounding_rate = 1 - unsupported_numeric / numeric_claims if numeric_claims else 1.0
    task_success_rate = (
        sum(1 for row in results if row.get("task_success")) / len(results)
        if results else 0.0
    )

    metrics = {
        "policy_accuracy": policy_accuracy,
        "blocked_cases": len(blocked_rows),
        "allowed_agent_cases": len(allowed_rows),
        "tool_exact_match_accuracy": tool_exact,
        "mean_tool_recall": tool_recall,
        "structured_citation_rate": citation_rate,
        "citation_in_answer_text_rate": citation_text_rate,
        "hallucination_proxy_case_rate": hallucination_proxy_case_rate,
        "numeric_grounding_rate": numeric_grounding_rate,
        "numeric_claim_count": numeric_claims,
        "unsupported_numeric_claim_count": unsupported_numeric,
        "task_success_rate": task_success_rate,
        "agent_latency": aggregate_latency(agent_latencies),
        "policy_latency": aggregate_latency(policy_latencies),
    }

    gates = dict(DEFAULT_GATES)
    gate_results = {
        "policy_accuracy": policy_accuracy >= gates["policy_accuracy_min"],
        "tool_exact_match_accuracy": (tool_exact or 0.0) >= gates["tool_exact_match_min"] if allowed_rows else policy_only,
        "mean_tool_recall": (tool_recall or 0.0) >= gates["tool_recall_min"] if allowed_rows else policy_only,
        "structured_citation_rate": (citation_rate or 0.0) >= gates["structured_citation_rate_min"] if allowed_rows else policy_only,
        "citation_in_answer_text_rate": (citation_text_rate or 0.0) >= gates["citation_text_rate_min"] if allowed_rows else policy_only,
        "hallucination_proxy_case_rate": (hallucination_proxy_case_rate or 0.0) <= gates["hallucination_proxy_case_rate_max"] if allowed_rows else policy_only,
        "allowed_latency_p95": (
            float(metrics["agent_latency"]["p95_ms"] or 0.0) <= gates["allowed_latency_p95_ms_max"]
            if allowed_rows else policy_only
        ),
    }

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "evaluation_scope": "policy_only" if policy_only else "agent_live",
        "case_count": len(results),
        "metrics": metrics,
        "acceptance_gates": gates,
        "gate_results": gate_results,
        "all_gates_passed": all(gate_results.values()),
        "hallucination_metric_note": (
            "Hallucination is reported as a deterministic proxy: numeric claims in the answer that are not grounded "
            "in the user prompt or captured tool evidence. It does not claim to detect every semantic hallucination."
        ),
    }
    return summary, results


def render_summary_markdown(summary: dict[str, Any]) -> str:
    m = summary["metrics"]
    gates = summary["gate_results"]

    def pct(value: Any) -> str:
        return "N/A" if value is None else f"{float(value) * 100:.1f}%"

    def ms(value: Any) -> str:
        return "N/A" if value is None else f"{float(value):.0f} ms"

    lines = [
        "# STEP 10 Agent Evaluation",
        "",
        f"- Generated: `{summary['generated_at']}`",
        f"- Scope: `{summary['evaluation_scope']}`",
        f"- Cases: **{summary['case_count']}**",
        f"- All acceptance gates: **{'PASS' if summary['all_gates_passed'] else 'FAIL'}**",
        "",
        "## Scorecard",
        "",
        "| Metric | Result | Gate |",
        "|---|---:|:---:|",
        f"| Privacy/policy accuracy | {pct(m['policy_accuracy'])} | {'PASS' if gates['policy_accuracy'] else 'FAIL'} |",
        f"| Tool exact-match accuracy | {pct(m['tool_exact_match_accuracy'])} | {'PASS' if gates['tool_exact_match_accuracy'] else 'FAIL'} |",
        f"| Mean tool recall | {pct(m['mean_tool_recall'])} | {'PASS' if gates['mean_tool_recall'] else 'FAIL'} |",
        f"| Structured citation/source trace rate | {pct(m['structured_citation_rate'])} | {'PASS' if gates['structured_citation_rate'] else 'FAIL'} |",
        f"| Citation present in answer text | {pct(m['citation_in_answer_text_rate'])} | {'PASS' if gates['citation_in_answer_text_rate'] else 'FAIL'} |",
        f"| Hallucination proxy case rate | {pct(m['hallucination_proxy_case_rate'])} | {'PASS' if gates['hallucination_proxy_case_rate'] else 'FAIL'} |",
        f"| Numeric grounding rate | {pct(m['numeric_grounding_rate'])} | info |",
        f"| Agent p50 latency | {ms(m['agent_latency']['p50_ms'])} | info |",
        f"| Agent p95 latency | {ms(m['agent_latency']['p95_ms'])} | {'PASS' if gates['allowed_latency_p95'] else 'FAIL'} |",
        f"| End-to-end task success | {pct(m['task_success_rate'])} | info |",
        "",
        "## Interpretation",
        "",
        summary["hallucination_metric_note"],
        "",
        "Tool and citation metrics are deterministic because the agent returns structured `tool_calls` and `sources`. "
        "Latency is measured wall-clock from LangGraph invocation through local Ollama and tool execution.",
    ]
    return "\n".join(lines) + "\n"
