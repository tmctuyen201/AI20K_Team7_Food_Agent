# Foodie Agent Chatbot — Phase 1

## Setup

```bash
# 1. Copy env
cp .env.example .env
# Edit .env and fill in your API keys

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python -m main.py
```

## Structure

```
app/
├── main.py              # CLI entry point (Phase 1)
├── core/
│   ├── config.py        # Settings from .env
│   ├── provider.py      # LLM provider config
│   ├── logging.py       # Structured logging
│   ├── exceptions.py    # Custom exceptions
│   └── guardrail.py     # Guardrail checks
├── agent/
│   ├── react_agent.py   # ReAct loop
│   ├── state.py         # AgentState
│   └── prompt.py        # System prompt
├── services/
│   ├── google_places.py # Places API client
│   ├── geocoding.py     # Geocoding API client
│   └── history.py       # History (Phase 1: stubs)
└── tools/
    ├── definitions.py   # LiteLLM tool specs
    ├── scoring.py       # Score & rank places
    └── mock_data.py     # 10 mock users
```

## Logging

All logs go to stdout. Per-session traces are written to `logs/session_<id>.log`.

## Phase Roadmap

- **Phase 1** (current): CLI chat, mock users, LLM + tools, logging ✅
- **Phase 2**: MongoDB integration, history
- **Phase 3**: WebSocket API, JWT auth
- **Phase 4**: Docker, deploy
