from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

from peoplepulse.agent.policy import evaluate_request
from peoplepulse.config import Settings, get_settings


_LOCK = threading.Lock()
_AGENTS: dict[str, Any] = {}


def _agent(settings: Settings, scope: str):
    from peoplepulse.agent.graph import AnalystAgent

    key = f"{scope}:{settings.agent_ollama_model}:{settings.agent_ollama_base_url}"
    with _LOCK:
        if key not in _AGENTS:
            _AGENTS[key] = AnalystAgent(settings, scope=scope)
        return _AGENTS[key]


def ollama_health(settings: Settings) -> dict[str, Any]:
    url = settings.agent_ollama_base_url.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "base_url": settings.agent_ollama_base_url, "error": str(exc)}
    names = [str(row.get("name")) for row in payload.get("models", [])]
    return {
        "status": "ok" if settings.agent_ollama_model in names or any(name.startswith(settings.agent_ollama_model + ":") for name in names) else "model_missing",
        "base_url": settings.agent_ollama_base_url,
        "configured_model": settings.agent_ollama_model,
        "models": names,
    }


def chat(message: str, *, scope: str, thread_id: str) -> dict[str, Any]:
    settings = get_settings()
    settings.validate_agent_runtime(scope=scope)
    decision = evaluate_request(message, scope=scope)
    if not decision.allowed:
        return {
            "answer": decision.reason,
            "blocked": True,
            "sources": ["peoplepulse.agent.policy"],
            "tool_calls": [],
            "model": settings.agent_ollama_model,
            "scope": scope,
            "thread_id": thread_id,
        }
    result = _agent(settings, scope).invoke(message, thread_id=thread_id)
    result["blocked"] = False
    return result

def evaluation_chat(message: str, *, scope: str, thread_id: str) -> dict[str, Any]:
    """Internal STEP 10 evaluator path. Evidence is never exposed by the public chat API."""
    settings = get_settings()
    settings.validate_agent_runtime(scope=scope)
    decision = evaluate_request(message, scope=scope)
    if not decision.allowed:
        return {
            "answer": decision.reason,
            "blocked": True,
            "sources": ["peoplepulse.agent.policy"],
            "tool_calls": [],
            "evidence": [],
            "model": settings.agent_ollama_model,
            "scope": scope,
            "thread_id": thread_id,
        }
    result = _agent(settings, scope).invoke(message, thread_id=thread_id, include_evidence=True)
    result["blocked"] = False
    return result

