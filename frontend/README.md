# Foodie Agent — Frontend

React + TypeScript + ViteJS frontend for the Foodie Agent chatbot.

## Setup

```bash
npm install
npm run dev
```

## Environment

Copy `.env.example` to `.env` and set:

```
VITE_BACKEND_URL=http://localhost:8000
```

## API Integration

Frontend connects to the FastAPI backend at `VITE_BACKEND_URL`.

### Authentication Flow

1. `POST /api/session` → create session + receive JWT
2. `ws://host/ws/chat?token=<jwt>` → WebSocket chat

### Endpoints Used

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/session` | Create session, get JWT |
| GET | `/api/history/{user_id}` | Get selection history |
| POST | `/api/selection` | Save a restaurant selection |
| WS | `/ws/chat?token=<jwt>` | Real-time chat with streaming |

## Scripts

```bash
npm run dev     # Development server on :3000
npm run build   # Production build
npm run preview # Preview production build
```
