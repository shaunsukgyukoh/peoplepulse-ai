# STEP 10 Agent Evaluation

- Generated: `2026-08-20T06:31:43.690117+00:00`
- Scope: `agent_live`
- Cases: **36**
- All acceptance gates: **FAIL**

## Scorecard

| Metric | Result | Gate |
|---|---:|:---:|
| Privacy/policy accuracy | 100.0% | PASS |
| Tool exact-match accuracy | 100.0% | PASS |
| Mean tool recall | 100.0% | PASS |
| Structured citation/source trace rate | 100.0% | PASS |
| Citation present in answer text | 95.0% | PASS |
| Hallucination proxy case rate | 65.0% | FAIL |
| Numeric grounding rate | 80.0% | info |
| Agent p50 latency | 9006 ms | info |
| Agent p95 latency | 14747 ms | FAIL |
| End-to-end task success | 100.0% | info |

## Interpretation

Hallucination is reported as a deterministic proxy: numeric claims in the answer that are not grounded in the user prompt or captured tool evidence. It does not claim to detect every semantic hallucination.

Tool and citation metrics are deterministic because the agent returns structured `tool_calls` and `sources`. Latency is measured wall-clock from LangGraph invocation through local Ollama and tool execution.
