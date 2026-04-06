"""Shared data models used across database, services, and tools."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


class LatLng(BaseModel):
    lat: float
    lng: float


class LocationResult(BaseModel):
    lat: float
    lng: float
    source: str = "unknown"
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserPreference(BaseModel):
    favorite_cuisines: list[str] = Field(default_factory=list)
    price_range: Optional[str] = None
    dietary_restrictions: list[str] = Field(default_factory=list)


class User(BaseModel):
    user_id: str
    name: str
    lat: float = 0.0
    lng: float = 0.0
    city: str = ""
    preference: UserPreference = Field(default_factory=UserPreference)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class Session(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    keyword: Optional[str] = None


# ---------------------------------------------------------------------------
# Selection (saved restaurant choice)
# ---------------------------------------------------------------------------


class Selection(BaseModel):
    user_id: str
    place_id: str
    name: str
    cuisine_type: Optional[str] = None
    rating: float = 0.0
    selected_at: datetime = Field(default_factory=datetime.utcnow)


class SelectionResponse(BaseModel):
    success: bool
    message: str = ""


# ---------------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------------


class Place(BaseModel):
    place_id: str = ""
    name: str = ""
    rating: float = 0.0
    distance_km: float = 0.0
    address: str = ""
    open_now: bool = False
    cuisine_type: Optional[str] = None


class ScoredPlace(Place):
    score: float = 0.0
