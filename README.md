# Foodie Agent Chatbot

A ReAct-based CLI chatbot that helps users find restaurants using Google Places API. The agent loop is powered by an LLM (OpenAI or Anthropic via LiteLLM) that decides when to call tools.

---

## Prerequisites

- Python 3.10+
- API keys:
  - OpenAI (`OPENAI_API_KEY`) **or** Anthropic (`ANTHROPIC_API_KEY`)
  - Google Places (`GOOGLE_PLACES_API_KEY`)

---

## Setup

### 1. Clone & configure environment variables

```bash
git clone <repo-url>
cd Day03-AI-Chatbot-labs
cp .env.example .env
```

Open `.env` and fill in your keys:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini-2024-08-06
OPENAI_API_KEY=sk-proj-...
# ANTHROPIC_API_KEY=sk-ant-...  # use instead of OPENAI_API_KEY if LLM_PROVIDER=anthropic

GOOGLE_PLACES_API_KEY=...
GOOGLE_GEOCODING_API_KEY=...

JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
```

### 2. Backend — create venv & install dependencies

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend — install dependencies

```bash
cd frontend
npm install
```

---

## Run

You need **two terminals** — one for the backend, one for the frontend.

### Terminal 1 — Backend (FastAPI)

```bash
# activate venv first
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux / macOS

uvicorn app.server:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. API docs: `http://localhost:8000/docs`.

### Terminal 2 — Frontend (Vite.js)

```bash
cd frontend
npm run dev
```

The UI will be available at `http://localhost:3000`.

> The frontend is pre-configured to proxy `/api/*` requests to `http://localhost:8000`.

---

## Project Structure

```
foodie-agent/
├── app/                      # Backend (FastAPI)
│   ├── server.py             # FastAPI entry point (uvicorn app.server:app)
│   ├── main.py               # Alternative FastAPI entry point
│   ├── api/                  # Route handlers (chat, history, session)
│   ├── agent/                # ReAct agent + LangGraph nodes & runner
│   │   └── sub_agents/      # Sub-agents (data_store, etc.)
│   ├── core/                 # Config, auth, logging, guardrails
│   ├── db/                   # Database layer (MongoDB + JSON fallback)
│   ├── services/             # Google Places, Geocoding, LLM clients
│   └── tools/                # Tool definitions, registry, scoring
├── frontend/                 # Frontend (Vite + React)
│   ├── src/
│   └── package.json
└── requirements.txt         # Python dependencies
```

---

## Architecture

### Agent Loop (`app/agent/`)

The agent runs on **LangGraph** with a ReAct-style node graph (`app/agent/graph.py` + `app/agent/nodes.py`):
- The LLM decides when to call tools
- Tool calls are handled by the **tool registry** (`app/tools/registry.py`)
- Each tool (places search, geocoding, scoring, memory) is a self-contained unit

### LLM Provider (`app/services/llm.py`)

LiteLLM is used as the LLM abstraction layer. **Model names must include a provider prefix** — `openai/gpt-4o-mini-2024-08-06`, not just `gpt-4o-mini`. Handled automatically by the LLM service.

**Tool-calling requires `stream=False`** — streaming does not support tool calls in LiteLLM.

### API (`app/api/`)

- `chat.py` — streaming chat endpoint (`POST /api/chat/stream`)
- `session.py` — session management (`POST /api/session/start`)
- `history.py` — conversation history (`GET /api/history/<session_id>`)

### Logging (`app/core/logging.py`)

Structured logging via `structlog`. Domain prefixes:
- `foodie.agent.*` — agent iterations, node transitions
- `foodie.llm.*` — LLM call start/complete/error
- `foodie.tools.*` — tool call start/success/error
- `foodie.google_places.*` — API request/response

### Data Store

Phase 1 uses a JSON file store (no MongoDB). To enable MongoDB, set `MONGODB_URI` in `.env` and restore the `connect_db`/`close_db` hooks in `app/server.py`.

---

## Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1     | ✅ Done | CLI chat, mock users, LLM + tools, logging |
| 2     | ✅ Done | FastAPI backend, JWT auth, JSON store (MongoDB optional) |
| 3     | ✅ Done | Vite + React frontend, CORS, health endpoints |
| 4     | 🔜 Next | MongoDB integration, Docker, deploy |
