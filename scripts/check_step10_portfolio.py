from __future__ import annotations

import json
from pathlib import Path

from peoplepulse.agent.policy import evaluate_request
from peoplepulse.evaluation.runner import DEFAULT_GATES, load_cases

REQUIRED = [
    "README.md",
    "docker-compose.yml",
    "scripts/portfolio_up.ps1",
    "scripts/portfolio_down.ps1",
    "scripts/run_step10_evaluation.py",
    "data/evaluation/step10_agent_eval_cases.jsonl",
    "docs/portfolio/architecture.md",
    "docs/portfolio/demo-scenario.md",
    "docs/portfolio/evaluation-methodology.md",
    "docs/portfolio/interview-guide.md",
    "docs/portfolio/portfolio-checklist.md",
]


def main() -> None:
    for path in REQUIRED:
        if not Path(path).exists():
            raise SystemExit(f"[ERROR] missing STEP 10 file: {path}")

    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    if compose.count('"portfolio"') < 6:
        raise SystemExit("[ERROR] portfolio compose profile is not attached to all required services")

    tools = Path("src/peoplepulse/agent/tools.py").read_text(encoding="utf-8").lower()
    if "@tool" not in tools:
        raise SystemExit("[ERROR] analyst tools missing")
    dangerous_signatures = ["drop table", "delete from", "update features.", "insert into features."]
    for token in dangerous_signatures:
        if token in tools:
            raise SystemExit(f"[ERROR] write SQL detected in agent tool layer: {token}")

    cases = load_cases("data/evaluation/step10_agent_eval_cases.jsonl")
    if len(cases) < 30:
        raise SystemExit("[ERROR] STEP 10 evaluation dataset must contain at least 30 cases")
    if not any(case.expected_blocked for case in cases) or not any(not case.expected_blocked for case in cases):
        raise SystemExit("[ERROR] evaluation dataset must include both allowed and blocked cases")

    policy_ok = 0
    for case in cases:
        decision = evaluate_request(case.message, scope=case.scope)
        policy_ok += int((not decision.allowed) == case.expected_blocked)
    if policy_ok != len(cases):
        raise SystemExit(f"[ERROR] deterministic policy gate failed {policy_ok}/{len(cases)}")

    readme = Path("README.md").read_text(encoding="utf-8")
    for heading in ("Quick Start", "Architecture", "Evaluation", "Privacy", "Demo", "Limitations"):
        if heading.lower() not in readme.lower():
            raise SystemExit(f"[ERROR] README missing portfolio section: {heading}")

    print("[OK] STEP 10 portfolio preflight")
    print(f"  evaluation_cases={len(cases)}")
    print(f"  deterministic_policy={policy_ok}/{len(cases)}")
    print("  agent_tools=allowlisted read-only")
    print("  compose_profile=portfolio")
    print("  live_agent_metrics=measured only after local evaluation; no fabricated score committed")
    print("  acceptance_gates=" + json.dumps(DEFAULT_GATES, ensure_ascii=False))


if __name__ == "__main__":
    main()
