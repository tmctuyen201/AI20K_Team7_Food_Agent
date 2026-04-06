"""FastAPI application entry point.

Phase 1: uses JSON file store (no MongoDB).
To enable MongoDB: set MONGODB_URI in .env and restore connect_db/close_db.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat_router, session_router, history_router
from app.core.logging import get_logger

logger = get_logger("foodie.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MongoDB startup is DISABLED — using JSON file store instead
    # To enable MongoDB:
    #   1. Set MONGODB_URI in .env
    #   2. Uncomment lines below
    #   3. Replace this lifespan with the one from server.py
    #
    # from app.db.connection import connect_db, close_db
    # await connect_db()
    logger.info("app_startup_complete", store="json")
    yield
    # await close_db()
    logger.info("app_shutdown_complete")


app = FastAPI(
    title="Foodie Agent API",
    description="ReAct-based chatbot for restaurant recommendations with streaming support.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──────────────────────────────────────────────────────────────────────

app.include_router(chat_router, tags=["chat"])
app.include_router(session_router, tags=["session"])
app.include_router(history_router, tags=["history"])


@app.get("/", tags=["root"])
async def root():
    """Root health check."""
    return {"message": "Foodie Agent API", "version": "1.0.0"}


@app.get("/health", tags=["root"])
async def health():
    """Basic liveness probe."""
    return {"status": "healthy"}
