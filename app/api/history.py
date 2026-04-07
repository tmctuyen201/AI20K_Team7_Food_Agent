"""History endpoints — uses JSON file store (Phase 1, no MongoDB)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.db.connection import users_store, selections_store

router = APIRouter()
logger = get_logger("foodie.api.history")


class SelectionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    place_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    cuisine_type: str | None = None
    rating: float = Field(default=0.0, ge=0.0, le=5.0)


class SelectionResponse(BaseModel):
    success: bool
    message: str


class ChatMessage(BaseModel):
    timestamp: str
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]


@router.get("/api/history/{user_id}")
async def get_history(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    # Get all selections for user
    selections = []
    for key, data in selections_store.items():
        if data.get("user_id") == user_id:
            selections.append(data)

    # Sort by selected_at descending
    selections.sort(key=lambda x: x.get("selected_at", ""), reverse=True)

    # Apply limit
    selections = selections[:limit]
    total = sum(1 for k, v in selections_store.items() if v.get("user_id") == user_id)

    # Count top cuisines
    cuisine_count: dict[str, int] = {}
    for sel in selections:
        cuisine = sel.get("cuisine_type") or "unknown"
        cuisine_count[cuisine] = cuisine_count.get(cuisine, 0) + 1

    top_cuisines = [
        {"cuisine": c, "count": cnt, "avg_rating": 0.0}
        for c, cnt in sorted(cuisine_count.items(), key=lambda x: -x[1])[:5]
    ]

    logger.info("history_fetched", user_id=user_id, returned=len(selections), total=total)

    return {
        "selections": selections,
        "total": total,
        "top_cuisines": top_cuisines,
    }


@router.post("/api/selection", response_model=SelectionResponse, status_code=status.HTTP_201_CREATED)
async def save_selection(request: SelectionRequest) -> SelectionResponse:
    now = datetime.utcnow().isoformat()
    selection_key = f"{request.user_id}:{request.place_id}"

    selection_data = {
        "user_id": request.user_id,
        "place_id": request.place_id,
        "name": request.name,
        "cuisine_type": request.cuisine_type,
        "rating": request.rating,
        "selected_at": now,
    }

    existing = selections_store.get(selection_key)
    if existing:
        # Update existing
        selections_store.set(selection_key, {**existing, **selection_data})
        logger.info("selection_updated", user_id=request.user_id, place_id=request.place_id)
    else:
        # Insert new
        selections_store.set(selection_key, selection_data)
        logger.info("selection_saved", user_id=request.user_id, place_id=request.place_id)

    # Update user's favorite cuisines
    if request.cuisine_type:
        user_data = users_store.get(request.user_id) or {}
        prefs = user_data.get("preference", {})
        fav_cuisines = prefs.get("favorite_cuisines", [])
        if request.cuisine_type not in fav_cuisines:
            fav_cuisines.append(request.cuisine_type)
        prefs["favorite_cuisines"] = fav_cuisines
        user_data["preference"] = prefs
        users_store.set(request.user_id, user_data)

    return SelectionResponse(success=True, message="Selection saved")


@router.get("/api/chat-history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str) -> ChatHistoryResponse:
    """Load chat history for a specific session from JSONL log file."""
    log_file = Path(__file__).parent.parent.parent / "logs" / f"agent_{session_id}.jsonl"
    
    if not log_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat history not found for session {session_id}"
        )
    
    messages = []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # Extract user messages from agent.step events
                if entry.get("event") == "agent.step":
                    message = entry.get("message", "")
                    timestamp = entry.get("timestamp", "")
                    
                    # Check if this is a user message (parsing intent)
                    if message.startswith("[Step 1] Parsing intent from:"):
                        user_content = message.replace("[Step 1] Parsing intent from:", "").strip()
                        if user_content:
                            messages.append(ChatMessage(
                                timestamp=timestamp,
                                role="user",
                                content=user_content
                            ))
                    
                    # Check if this is an assistant response
                    elif message.startswith("[Final Response]"):
                        assistant_content = message.replace("[Final Response]", "").strip()
                        if assistant_content:
                            messages.append(ChatMessage(
                                timestamp=timestamp,
                                role="assistant",
                                content=assistant_content
                            ))
    
    except Exception as e:
        logger.error("error_reading_chat_history", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading chat history: {str(e)}"
        )
    
    logger.info("chat_history_loaded", session_id=session_id, message_count=len(messages))
    
    return ChatHistoryResponse(
        session_id=session_id,
        messages=messages
    )
