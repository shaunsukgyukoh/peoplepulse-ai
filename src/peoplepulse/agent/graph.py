from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from peoplepulse.agent.policy import system_prompt
from peoplepulse.agent.tools import build_tools
from peoplepulse.config import Settings


class AnalystAgent:
    def __init__(self, settings: Settings, *, scope: str):
        self.settings = settings
        self.scope = scope
        self.tools = build_tools(settings, scope=scope)
        self.tool_names = {tool.name for tool in self.tools}
        llm = ChatOllama(
            model=settings.agent_ollama_model,
            base_url=settings.agent_ollama_base_url,
            temperature=settings.agent_temperature,
            num_ctx=settings.agent_num_ctx,
        )
        bound = llm.bind_tools(self.tools)

        def call_model(state: MessagesState) -> dict[str, list[Any]]:
            messages = [SystemMessage(content=system_prompt(scope)), *state["messages"]]
            return {"messages": [bound.invoke(messages)]}

        builder = StateGraph(MessagesState)
        builder.add_node("analyst", call_model)
        builder.add_node("tools", ToolNode(self.tools, handle_tool_errors=True))
        builder.add_edge(START, "analyst")
        builder.add_conditional_edges("analyst", tools_condition, {"tools": "tools", END: END})
        builder.add_edge("tools", "analyst")
        self.checkpointer = InMemorySaver()
        self.graph = builder.compile(checkpointer=self.checkpointer)

    def invoke(self, message: str, *, thread_id: str) -> dict[str, Any]:
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=message)]},
            {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": self.settings.agent_recursion_limit,
            },
        )
        messages = result.get("messages", [])
        answer = ""
        sources: list[str] = []
        tool_calls: list[str] = []
        for item in messages:
            if isinstance(item, ToolMessage):
                tool_calls.append(item.name or "tool")
                try:
                    payload = json_loads_maybe(item.content)
                except Exception:
                    payload = None
                if isinstance(payload, dict) and payload.get("source"):
                    sources.append(str(payload["source"]))
        if messages:
            answer = str(getattr(messages[-1], "content", "") or "")
        return {
            "answer": answer,
            "sources": sorted(set(sources)),
            "tool_calls": tool_calls[-20:],
            "model": self.settings.agent_ollama_model,
            "scope": self.scope,
            "thread_id": thread_id,
        }


def json_loads_maybe(value: Any) -> Any:
    import json

    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, list):
        text = "".join(str(part.get("text", "")) for part in value if isinstance(part, dict))
        return json.loads(text)
    return value
