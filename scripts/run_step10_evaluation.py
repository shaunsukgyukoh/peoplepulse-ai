from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from peoplepulse.evaluation.runner import evaluate_cases, load_cases, render_summary_markdown


def write_results(output_root: Path, summary: dict, rows: list[dict], *, publish: bool) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "summary.md").write_text(render_summary_markdown(summary), encoding="utf-8")
    with (run_dir / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    flat_rows = []
    for row in rows:
        flat_rows.append(
            {
                "id": row["id"],
                "scope": row["scope"],
                "expected_blocked": row["expected_blocked"],
                "policy_ok": row["policy_ok"],
                "task_success": row.get("task_success"),
                "agent_latency_ms": row.get("agent_latency_ms"),
                "tool_exact_match": (row.get("tool_metrics") or {}).get("exact_match"),
                "tool_recall": (row.get("tool_metrics") or {}).get("recall"),
                "structured_citation": row.get("structured_citation"),
                "citation_in_answer_text": row.get("citation_in_answer_text"),
                "hallucination_proxy": (row.get("grounding") or {}).get("hallucination_proxy"),
                "unsupported_numeric_claims": (row.get("grounding") or {}).get("unsupported_numeric_claims"),
            }
        )
    with (run_dir / "cases.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat_rows[0].keys()) if flat_rows else ["id"])
        writer.writeheader()
        writer.writerows(flat_rows)

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "latest_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_root / "latest_summary.md").write_text(render_summary_markdown(summary), encoding="utf-8")

    if publish:
        docs = Path("docs/portfolio")
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "agent-evaluation-results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (docs / "agent-evaluation-results.md").write_text(render_summary_markdown(summary), encoding="utf-8")
        print("[OK] published measured evaluation to docs/portfolio/agent-evaluation-results.*")

    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="PeoplePulse STEP 10 agent evaluation")
    parser.add_argument("--dataset", default="data/evaluation/step10_agent_eval_cases.jsonl")
    parser.add_argument("--output-root", default="artifacts/evaluation/step10")
    parser.add_argument("--policy-only", action="store_true", help="Run deterministic policy cases without Ollama/tool calls")
    parser.add_argument("--publish", action="store_true", help="Copy the measured summary into docs/portfolio for a portfolio commit")
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    summary, rows = evaluate_cases(cases, policy_only=args.policy_only)
    run_dir = write_results(Path(args.output_root), summary, rows, publish=args.publish)
    print(render_summary_markdown(summary))
    print(f"[OK] STEP 10 evaluation artifacts: {run_dir}")
    if not summary["all_gates_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
