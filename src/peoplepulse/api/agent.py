from __future__ import annotations

import re
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from peoplepulse.agent.service import chat, ollama_health
from peoplepulse.config import get_settings

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    scope: Literal["aggregate", "synthetic_demo"] = "aggregate"
    thread_id: str | None = Field(default=None, max_length=80)


_THREAD_RE = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")


@router.get("/health")
def agent_health() -> dict:
    return ollama_health(get_settings())


@router.post("/chat")
def agent_chat(payload: ChatRequest) -> dict:
    thread_id = payload.thread_id or uuid.uuid4().hex
    if not _THREAD_RE.fullmatch(thread_id):
        raise HTTPException(status_code=422, detail="thread_id contains unsupported characters")
    try:
        return chat(payload.message, scope=payload.scope, thread_id=thread_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Analyst agent unavailable: {exc}") from exc
