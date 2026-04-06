"""FastAPI server — Phase 2 entry point.

Run with: uvicorn app.server:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, history, session
from app.core.logging import get_logger

logger = get_logger("foodie.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("server_startup")
    yield
    logger.info("server_shutdown")


app = FastAPI(
    title="Foodie Agent API",
    description="ReAct chatbot for restaurant discovery",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(session.router, tags=["Session"])
app.include_router(history.router, tags=["History"])
app.include_router(chat.router, tags=["Chat"])


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Lightweight health check — useful for container orchestration."""
    return {"status": "healthy", "version": "0.2.0"}
