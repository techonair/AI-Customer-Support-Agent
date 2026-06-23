"""
FastAPI backend for the ShopEase Refund Agent.

Endpoints:
  POST /api/chat/stream  — SSE stream of agent log events + final message
  GET  /api/health       — health check
  GET  /                 — serves static/index.html

Run with:
  uvicorn server:app --reload --port 8000
"""

import json
import queue
import threading
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.loop import run_agent_loop
from data.customers import CUSTOMERS
from data.orders import ORDERS

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="ShopEase Refund Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request schema ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]
    """
    Full conversation history sent by the client.
    Each item is {"role": "user"|"assistant", "content": "..."}.
    The system prompt is injected server-side in the agent loop.
    """


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "agent": "ShopEase Refund Agent v1.0"}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Run the agent loop and stream events back as Server-Sent Events (SSE).

    Event types emitted:
      {"type": "log",     "data": {type, message, tool?, input?, result?}}
      {"type": "message", "content": "<final agent reply>"}
      {"type": "error",   "content": "<error message>"}
    """
    log_q: queue.Queue = queue.Queue()
    result_box: dict = {"message": None, "error": None}

    def worker():
        def on_log(entry: dict):
            log_q.put({"type": "log", "data": entry})

        try:
            reply = run_agent_loop(req.messages, on_log=on_log)
            result_box["message"] = reply
        except Exception as exc:
            result_box["error"] = str(exc)
        finally:
            log_q.put({"type": "__done__"})

    # why threading.Thread instead of asyncio.create_task? Because run_agent_loop is synchronous and blocking, so we need a separate thread to avoid blocking the FastAPI event loop.
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def generate():
        while True:
            try:
                item = log_q.get(timeout=60)   # 60-second safety timeout
            except queue.Empty:
                yield _sse({"type": "error", "content": "Agent timed out"})
                break

            if item["type"] == "__done__":
                if result_box["error"]:
                    yield _sse({"type": "error", "content": result_box["error"]})
                else:
                    yield _sse({"type": "message", "content": result_box["message"]})
                break
            else:
                yield _sse(item)

        thread.join(timeout=5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


# ── CRM data endpoint (used by the frontend CRM tab) ─────────────────────────

@app.get("/api/crm")
def get_crm():
    return {"customers": list(CUSTOMERS.values()), "orders": ORDERS}


# ── Static files (must be last) ───────────────────────────────────────────────
# Serves static/index.html at GET /
app.mount("/", StaticFiles(directory="static", html=True), name="static")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    """Encode a dict as a Server-Sent Events data line."""
    return f"data: {json.dumps(payload)}\n\n"
