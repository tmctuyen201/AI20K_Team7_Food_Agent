"""FastAPI server — Phase 1/2 entry point.

Uses JSON file store for Phase 1 (no MongoDB required).
To enable MongoDB: set MONGODB_URI in .env and uncomment lifespan hooks.

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
    # MongoDB startup is DISABLED — using JSON file store instead
    # To enable MongoDB:
    #   1. Set MONGODB_URI in .env
    #   2. Uncomment lines below
    #   3. Add connect_db() / close_db() here
    #
    # from app.db.connection import connect_db, close_db
    # await connect_db()
    logger.info("server_startup", store="json")
    yield
    # await close_db()
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
    return {"status": "healthy", "version": "0.2.0", "store": "json"}
