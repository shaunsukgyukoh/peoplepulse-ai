from __future__ import annotations

import json
from pathlib import Path

from peoplepulse.agent.policy import evaluate_request
from peoplepulse.evaluation.runner import load_cases


def main() -> None:
    cases = load_cases("data/evaluation/step10_agent_eval_cases.jsonl")
    rows = []
    passed = 0
    for case in cases:
        decision = evaluate_request(case.message, scope=case.scope)
        ok = (not decision.allowed) == case.expected_blocked
        passed += int(ok)
        rows.append({
            "id": case.id,
            "scope": case.scope,
            "expected_blocked": case.expected_blocked,
            "allowed": decision.allowed,
            "ok": ok,
            "reason": decision.reason,
        })
    accuracy = passed / len(cases) if cases else 0.0
    output = {
        "cases": len(cases),
        "passed": passed,
        "accuracy": accuracy,
        "required": 1.0,
        "status": "PASS" if accuracy == 1.0 else "FAIL",
        "rows": rows,
    }
    path = Path("artifacts/evaluation/step10/policy_latest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Policy cases: {passed}/{len(cases)} ({accuracy:.1%})")
    print(f"Status: {output['status']}")
    if accuracy != 1.0:
        for row in rows:
            if not row["ok"]:
                print(f"[FAIL] {row['id']} expected_blocked={row['expected_blocked']} allowed={row['allowed']}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
