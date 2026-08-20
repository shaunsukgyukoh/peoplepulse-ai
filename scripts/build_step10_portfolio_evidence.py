from __future__ import annotations

import json
from pathlib import Path


def fmt(value: float | None, digits: int = 3) -> str:
    return "N/A" if value is None else f"{value:.{digits}f}"


def main() -> None:
    nlp = json.loads(Path("docs/experiment-results/nlp_model_comparison_step3_1.json").read_text(encoding="utf-8"))
    step6 = json.loads(Path("docs/experiment-results/step6_reference_metrics.json").read_text(encoding="utf-8"))
    agent_path = Path("artifacts/evaluation/step10/latest_summary.json")
    agent = json.loads(agent_path.read_text(encoding="utf-8")) if agent_path.exists() else None

    best_nlp = nlp[0]
    privacy_safe = step6["feature_set_comparison"][0]
    lines = [
        "# PeoplePulse AI — Portfolio Evidence Summary",
        "",
        "## Reproducible evidence already committed",
        "",
        f"- STEP 3 synthetic NLP benchmark: `{best_nlp['model']}` Macro-F1 **{best_nlp['macro_f1']:.3f}**, p95 **{best_nlp['latency_ms_p95']:.2f} ms** on `{best_nlp['device']}`.",
        f"- STEP 6 synthetic attrition temporal test: AP **{privacy_safe['average_precision']:.4f}**, ROC-AUC **{privacy_safe['roc_auc']:.4f}**, Recall@Top10% **{privacy_safe['recall_at_top_10pct']:.4f}**.",
        "- STEP 10 deterministic privacy/policy dataset: 36 cases, required gate 100%.",
        "",
        "## Live local Agent evaluation",
        "",
    ]
    if agent and agent.get("evaluation_scope") == "agent_live":
        m = agent["metrics"]
        lines.extend([
            f"- Tool exact-match: **{fmt(m.get('tool_exact_match_accuracy'))}**",
            f"- Mean tool recall: **{fmt(m.get('mean_tool_recall'))}**",
            f"- Structured citation rate: **{fmt(m.get('structured_citation_rate'))}**",
            f"- Citation in answer text: **{fmt(m.get('citation_in_answer_text_rate'))}**",
            f"- Hallucination proxy case rate: **{fmt(m.get('hallucination_proxy_case_rate'))}**",
            f"- Numeric grounding rate: **{fmt(m.get('numeric_grounding_rate'))}**",
            f"- Agent p95 latency: **{fmt(m.get('agent_latency', {}).get('p95_ms'), 0)} ms**",
            f"- Acceptance gates: **{'PASS' if agent.get('all_gates_passed') else 'FAIL'}**",
        ])
    else:
        lines.extend([
            "Live tool/citation/hallucination/latency metrics are not committed yet.",
            "Run `python scripts/run_step10_evaluation.py --publish` on the demo machine after Ollama and the portfolio stack are healthy.",
        ])
    lines.extend([
        "",
        "## Evidence discipline",
        "",
        "- Synthetic benchmark numbers are labeled synthetic.",
        "- No live Agent score is fabricated before local measurement.",
        "- Failed evaluation gates should be kept visible and discussed with the corresponding failed cases.",
    ])
    output = Path("docs/portfolio/portfolio-evidence.md")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] wrote {output}")


if __name__ == "__main__":
    main()
