# ShopEase AI Refund Agent

AI-powered e-commerce customer support agent that processes refund requests using **OpenAI GPT-4o function calling** — no LangGraph or CrewAI, just the raw API loop that powers all agent frameworks.

## Stack
| Layer | Tech |
|---|---|
| LLM | llama-3.3-70b-versatile (function calling) |
| Backend | Python · FastAPI · SSE streaming |
| Frontend | Vanilla JS · single HTML file · Web Speech API |
| Agent pattern | Raw function-calling loop (4 tools) |

## Project Structure
```
shopease-refund-agent/
├── server.py              ← FastAPI app + SSE endpoint
├── requirements.txt
├── .env.example
├── agent/
│   ├── loop.py            ← Agent loop (function-calling iteration)
│   ├── tools.py           ← OpenAI tool definitions (JSON schema)
│   ├── executor.py        ← Tool execution engine (pure Python)
│   └── system_prompt.py   ← System prompt injected into every call
├── data/
│   ├── customers.py       ← 15 mock CRM profiles
│   ├── orders.py          ← 15 mock orders (covers all policy edge cases)
│   └── policy.py          ← Refund policy document + TODAY constant
└── static/
    └── index.html         ← Full UI (chat + admin dashboard + voice)
```

## Quick Start

```bash
# 1. Clone / unzip the project
cd shopease-refund-agent

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your OpenAI API key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# 5. Start the server
uvicorn server:app --reload --port 8000

# 6. Open in browser
open http://localhost:8000
```

## Test Scenarios

| Scenario | Customer | Order | Expected Decision |
|---|---|---|---|
| Defective electronics | Alice Johnson | ORD-1001 | ✅ APPROVED (defective overrides 15-day window) |
| Expired return window | Frank Miller | ORD-1006 | ❌ DENIED (85 days, §1) |
| Digital product | David Wilson | ORD-1004 | ❌ DENIED (§1 digital non-refundable) |
| High-value defective TV | Grace Lee | ORD-1007 | 🔶 ESCALATED ($799.99 > $500, §3) |
| Final sale jeans | Liam Jackson | ORD-1012 | ❌ DENIED (§4 FINAL SALE) |
| Personalized item | Isabella Anderson | ORD-1009 | ❌ DENIED (§4 customized) |
| Fraud-flagged account | Carol Davis | ORD-1003 | 🔶 ESCALATED (flagged, §5) |

## How the Agent Loop Works

```
User message
     │
     ▼
┌─────────────────────────────────────┐
│  LLAMA  (system prompt + tools)    │
└─────────────────────────────────────┘
     │
     ├── tool_calls present? ──YES──► execute_tool() locally
     │                                      │
     │                          append tool result to conversation
     │                                      │
     └──────────────────────────────────────┘ (loop)
     │
     └── No tool calls → final text response → SSE → UI
```

The four tools mirror a real CRM + policy system:
- `search_customer` — fuzzy match on name, email, phone, or ID
- `get_order_details` — fetch by order ID or list by customer
- `validate_refund_eligibility` — full policy engine (windows, exclusions, fraud)
- `process_refund_decision` — commits APPROVED / DENIED / ESCALATED

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat/stream` | SSE stream: log events + final message |
| `GET` | `/api/health` | Health check |
| `GET` | `/` | Frontend UI |

## Voice Input

The UI uses the browser's native `SpeechRecognition` API (Chrome / Edge). No extra API key required. Click the 🎤 button and speak your refund request.

## Extending

**Add streaming text output** — replace `max_tokens` with `stream=True` in `loop.py` and yield token chunks via SSE.

**Add voice output** — pipe the final agent response to the OpenAI TTS endpoint (`client.audio.speech.create`) or ElevenLabs for a full duplex voice pipeline.

**Add a real database** — swap `data/customers.py` and `data/orders.py` with SQLAlchemy models; the executor functions are the only files that need changing.
