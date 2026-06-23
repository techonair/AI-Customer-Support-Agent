"""
Agent loop — now powered by LangGraph.

Replaces the hand-rolled while-loop with graph.stream(), which iterates
through StateGraph nodes and emits update events after each node fires.

Event shape from graph.stream(mode="updates"):
  { "agent": {"messages": [AIMessage(...)]} }   — LLM responded
  { "tools": {"messages": [ToolMessage(...)]} }  — tools executed

We translate these events into log entries for the SSE stream so the
admin dashboard can show real-time reasoning without any extra plumbing.
"""

import json
from collections.abc import Callable

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.graph import graph


# ── Public API ────────────────────────────────────────────────────────────────

def run_agent_loop(
    messages: list[dict],
    on_log: Callable[[dict], None] | None = None,
) -> str:
    """
    Run the LangGraph refund agent for one conversation turn.

    Args:
        messages:  Full conversation history as plain dicts
                   [{"role": "user"|"assistant", "content": "..."}].
                   The system prompt is injected inside graph.py.
        on_log:    Optional callback invoked after every meaningful graph
                   event — used to stream reasoning logs to the UI via SSE.

    Returns:
        The agent's final plain-text reply to the customer.
    """
    # Convert dict messages → LangChain message objects
    lc_messages = _to_lc_messages(messages)

    final_text: str | None = None

    # ── Stream through the graph, node by node ────────────────────────────────
    # stream_mode="updates" yields one dict per node that ran:
    #   {"node_name": <state_update_dict>}
    for event in graph.stream(
        {"messages": lc_messages},
        stream_mode="updates",
    ):
        for node_name, node_output in event.items():
            node_msgs = node_output.get("messages", [])

            # ── agent node fired ──────────────────────────────────────────────
            if node_name == "agent":
                # The last message from the agent node is either a final answer (no tool calls)
                last = node_msgs[-1] if node_msgs else None
                if not isinstance(last, AIMessage):
                    continue

                if last.tool_calls:
                    # Model wants to call tools — log each one
                    _log(on_log, "api_call",
                         f"llama-3.3 → requesting {len(last.tool_calls)} tool call(s)")
                    for tc in last.tool_calls:
                        _log(on_log, "tool_call",
                             f"→ {tc['name']}({_truncate(tc['args'])})",
                             tool=tc["name"], input=tc["args"])
                else:
                    # No tool calls → this is the final answer
                    _log(on_log, "reasoning", "Agent produced final response")
                    final_text = last.content

            # ── tools node fired ──────────────────────────────────────────────
            elif node_name == "tools":
                for msg in node_msgs:
                    if not isinstance(msg, ToolMessage):
                        continue
                    try:
                        result = json.loads(msg.content)
                    except (json.JSONDecodeError, TypeError):
                        result = {"raw": str(msg.content)}

                    _log(on_log, "tool_result",
                         f"← {msg.name} returned",
                         tool=msg.name, result=result)

    return final_text or "I've completed processing your request."


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_lc_messages(messages: list[dict]):
    """Convert plain dicts to LangChain message objects."""
    result = []
    for m in messages:
        role    = m.get("role", "user")
        content = m.get("content", "")
        if role == "user":
            result.append(HumanMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
        # tool / system roles are handled internally by the graph
    return result


def _log(callback: Callable | None, log_type: str, message: str, **extra) -> None:
    if callback:
        callback({"type": log_type, "message": message, **extra})


def _truncate(obj, limit: int = 80) -> str:
    s = json.dumps(obj)
    return s[:limit] + "…" if len(s) > limit else s
