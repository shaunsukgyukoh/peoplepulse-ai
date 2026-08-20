from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str) -> Path:
    target = ROOT / path
    if not target.exists():
        raise SystemExit(f"[ERROR] missing STEP 9 file: {path}")
    return target


def main() -> int:
    pyproject = tomllib.loads(require("pyproject.toml").read_text(encoding="utf-8"))
    agent_deps = pyproject["project"]["optional-dependencies"]["agent"]
    joined = "\n".join(agent_deps)
    for dep in ("langchain>=1.3.14", "langchain-ollama>=1.1.0", "langgraph>=1.2.10"):
        if dep not in joined:
            raise SystemExit(f"[ERROR] agent dependency missing: {dep}")

    for path in (
        "src/peoplepulse/agent/policy.py",
        "src/peoplepulse/agent/tools.py",
        "src/peoplepulse/agent/graph.py",
        "src/peoplepulse/agent/service.py",
        "src/peoplepulse/api/agent.py",
        "dashboard/app/page.tsx",
        "scripts/setup_step9_ollama.ps1",
    ):
        require(path)

    for path in ROOT.glob("src/peoplepulse/agent/*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    tools = require("src/peoplepulse/agent/tools.py").read_text(encoding="utf-8").lower()
    forbidden = ("drop table", "delete from", "update features.", "insert into", "raw slack", "select * from features.synthetic")
    for token in forbidden:
        if token in tools:
            raise SystemExit(f"[ERROR] unsafe agent tool token detected: {token}")
    if "features.department_monthly_fusion" not in tools:
        raise SystemExit("[ERROR] aggregate Feature Store tool missing")
    if "demo-* synthetic key" not in require("src/peoplepulse/agent/tools.py").read_text(encoding="utf-8"):
        raise SystemExit("[ERROR] synthetic demo key guard missing")

    compose = require("docker-compose.yml").read_text(encoding="utf-8")
    if "host.docker.internal:11434" not in compose:
        raise SystemExit("[ERROR] Docker API is not wired to host-native Ollama")

    print("[OK] STEP 9 static preflight")
    print("  default_model=qwen3:8b")
    print("  orchestration=LangGraph StateGraph + ToolNode")
    print("  llm=host-native Ollama")
    print("  tools=fixed read-only analytics queries; no arbitrary SQL")
    print("  production_scope=department/cohort aggregate")
    print("  employee_scope=synthetic_demo demo-* only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
