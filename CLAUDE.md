# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Foodie Agent is a ReAct-based chatbot that helps users find restaurants using Google Places API. Phase 1 runs as a CLI terminal application. The agent loop is managed by an LLM (OpenAI or Anthropic via LiteLLM) that decides when to call tools.

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate        # Windows

pip install -r requirements.txt
cp .env.example .env           # Then edit .env with API keys

# Run CLI chat
py main.py

# Or use scripts
bash scripts/setup.sh          # Linux/macOS
scripts\setup.bat             # Windows
```

## Architecture

### ReAct Loop (`app/agent/react_agent.py`)

The core loop in `ReActAgent.run()`:
1. LLM receives messages + tool definitions
2. If LLM returns a tool call → execute it → feed result back → loop
3. If LLM returns text (no tool call) → agent is done

Tool routing is handled by `_route_tool()` which maps tool names to handler methods on the agent class. Each handler reads/writes `AgentState` (TypedDict) and returns a JSON string.

### LLM Provider (`app/core/provider.py`)

LiteLLM is used as the LLM abstraction layer. **Critical: LiteLLM requires provider prefix on model names** — `openai/gpt-4o-mini` not just `gpt-4o-mini`. This is handled automatically by `_resolve_model()`.

**Tool-calling requires `stream=False`** — streaming does not support tool use in LiteLLM. This is enforced in both `llm_chat` and `llm_chat_sync`.

### Logging (`app/core/logging.py`)

Structured logging via `structlog`. All events are prefixed by domain:
- `foodie.agent.*` — agent iterations, guardrail triggers
- `foodie.llm.*` — LLM call start/complete/error
- `foodie.tools.*` — tool call start/success/error
- `foodie.google_places.*` — API request/response

Use `get_logger("foodie.<domain>")` or the convenience helpers `get_agent_logger()`, `get_llm_logger()`, `get_tool_logger()`.

### Configuration (`app/core/config.py`)

All settings come from `.env` via `pydantic-settings`. The global `settings` singleton is imported throughout the codebase. Never hardcode credentials.

### Tool Definitions (`app/tools/definitions.py`)

LiteLLM-compatible JSON schemas. **Array types must include `items` key** — `{"type": "array", "items": {"type": "object"}}` not `{"type": "array"}`. Missing `items` causes `BadRequestError`.

### Phase Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1     | ✅ Done | CLI, mock users, LLM + tools, logging |
| 2     | 🔜 Next | MongoDB integration |
| 3     | 🔜 Next | FastAPI + WebSocket + JWT |
| 4     | 🔜 Next | Docker + deploy |

`app/services/history.py` contains stubs (Phase 1). When adding MongoDB (Phase 2), replace the stub functions there.

## Adding a New Tool

1. Add the schema to `app/tools/definitions.py` (include `items` for arrays)
2. Add a handler method to `ReActAgent` in `app/agent/react_agent.py`
3. Register it in `_route_tool()` dict
4. If the tool needs to persist data, implement it in `app/services/history.py` (Phase 2) or use the existing stubs (Phase 1)

## Environment Variables

Required in `.env`:
- `LLM_PROVIDER` — `openai` or `anthropic`
- `LLM_MODEL` — model name (e.g. `gpt-4o-mini`)
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- `GOOGLE_PLACES_API_KEY`

Do not commit `.env` — it is in `.gitignore`. Use `.env.example` as a template.
