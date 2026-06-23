"""
LangGraph StateGraph for the ShopEase Refund Agent.

Graph topology:

    [START]
       │
       ▼
   ┌──────┐     tool_calls present?
   │agent │ ──────────── YES ──────────► ┌───────┐
   └──────┘                              │ tools │
       ▲                                 └───────┘
       │                                     │
       └─────────────────────────────────────┘
       │
       │  no tool_calls (final answer)
       ▼
     [END]

Nodes:
  agent — calls LLM model with the full message history + system prompt.
           The model either produces a plain-text reply (→ END) or
           requests one or more tool calls (→ tools).

  tools — LangGraph's built-in ToolNode executes every tool call in
           the last AIMessage and appends ToolMessage results to state.
           Control always returns to the agent node.

State:
  A single key `messages` using LangGraph's `add_messages` reducer,
  which appends new messages rather than replacing the list.
"""

from typing import Annotated, TypedDict

import os

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.lc_tools import LANGCHAIN_TOOLS
from agent.system_prompt import SYSTEM_PROMPT


# ── Agent state ───────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """
    The only state the graph carries is the conversation message list.
    `add_messages` is a LangGraph reducer: new messages are *appended*
    rather than replacing the whole list on each node update.
    """
    messages: Annotated[list[BaseMessage], add_messages]


# ── LLM with tools bound ──────────────────────────────────────────────────────

# Instantiate LLM using environment-configurable model and OpenAI-compatible endpoint
# This lets Groq's OpenAI-compatible API be used via LLAMA_API_BASE_URL / LLAMA_API_KEY
_model_name = os.environ.get("OPENAI_DEFAULT_MODEL", "o1")
_openai_api_base = os.environ.get("LLAMA_API_BASE_URL")
_openai_api_key = os.environ.get("LLAMA_API_KEY")
_llm_kwargs = {}
if _openai_api_base:
    _llm_kwargs["openai_api_base"] = _openai_api_base
if _openai_api_key:
    _llm_kwargs["openai_api_key"] = _openai_api_key

_llm = ChatOpenAI(model=_model_name, temperature=0, **_llm_kwargs).bind_tools(LANGCHAIN_TOOLS)


# ── Node: agent ───────────────────────────────────────────────────────────────

def agent_node(state: AgentState) -> dict:
    """
    Call LLM with the system prompt prepended to the current message list.
    Returns the model's response (may contain tool_calls or a final answer).
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = _llm.invoke(messages)
    return {"messages": [response]}


# ── Edge condition ────────────────────────────────────────────────────────────

def should_continue(state: AgentState) -> str:
    """
    Route to 'tools' if the last AIMessage has tool calls, otherwise END.
    This is the conditional edge that drives the agent loop.
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


# ── Build and compile the graph ───────────────────────────────────────────────

def build_graph():
    builder = StateGraph(AgentState)

    # Nodes
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(LANGCHAIN_TOOLS))   # built-in tool executor

    # Edges
    builder.set_entry_point("agent") # entry point is the agent node
    builder.add_conditional_edges( # conditional edge from agent to either tools or END
        "agent",
        should_continue,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "agent")   # tools always returns to agent after executing tool calls

    return builder.compile()


# Module-level compiled graph (imported by loop.py)
graph = build_graph()
