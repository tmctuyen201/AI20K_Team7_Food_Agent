"""Shared data models used across database, services, and tools."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


class LatLng(BaseModel):
    lat: float
    lng: float

    def to_dict(self) -> dict:
        return {"lat": self.lat, "lng": self.lng}


class LocationResult(BaseModel):
    lat: float
    lng: float
    source: str = "unknown"
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# User preference
# ---------------------------------------------------------------------------


class UserPreference(BaseModel):
    """Per-user preference profile."""
    favorite_cuisines: list[str] = Field(default_factory=list)
    avoid_cuisines: list[str] = Field(default_factory=list)
    price_range: str = Field(default="mid")
    preferred_ambiance: Optional[str] = None
    dietary_restrictions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class User(BaseModel):
    """Application user."""
    user_id: str
    name: str = ""
    default_location: Optional[LatLng] = None
    preference: UserPreference = Field(default_factory=UserPreference)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class Session(BaseModel):
    """Chat session."""
    session_id: str
    user_id: str
    location: Optional[LatLng] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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


class Place(BaseModel, extra="ignore"):
    """A restaurant / place returned from Google Places API."""

    place_id: str = ""
    name: str = ""
    rating: float = 0.0
    distance_km: float = 0.0
    address: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    open_now: bool = False
    price_level: Optional[int] = None
    types: list[str] = Field(default_factory=list)
    photo_refs: list[str] = Field(default_factory=list)
    cuisine_type: Optional[str] = None
    distance_meters: Optional[float] = None
    next_page_token: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "place_id": self.place_id,
            "name": self.name,
            "rating": self.rating,
            "distance_km": self.distance_km,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "open_now": self.open_now,
            "price_level": self.price_level,
            "types": self.types,
            "photo_refs": self.photo_refs,
            "cuisine_type": self.cuisine_type,
            "distance_meters": self.distance_meters,
            "next_page_token": self.next_page_token,
        }

    @classmethod
    def from_google_result(cls, result: dict[str, Any]) -> "Place":
        """Construct a Place from a raw Google Places API result dict."""
        geometry = result.get("geometry") or {}
        location = geometry.get("location") or {}
        opening_hours = result.get("opening_hours") or {}
        distance_meters = geometry.get("distance_meters")
        distance_km = round(distance_meters / 1000, 2) if distance_meters else 0.0

        return cls(
            place_id=result.get("place_id", ""),
            name=result.get("name", ""),
            rating=float(result.get("rating") or 0.0),
            address=result.get("vicinity") or result.get("formatted_address", ""),
            latitude=location.get("lat"),
            longitude=location.get("lng"),
            open_now=bool(opening_hours.get("open_now")),
            price_level=result.get("price_level"),
            types=result.get("types") or [],
            photo_refs=[
                p.get("photo_reference", "")
                for p in (result.get("photos") or [])
            ],
            cuisine_type=result.get("cuisine_type"),
            distance_meters=distance_meters,
            distance_km=distance_km,
            next_page_token=result.get("_next_page_token"),
        )


class ScoredPlace(Place):
    """A Place with a computed relevance score and distance."""

    score: float = 0.0

    @classmethod
    def from_scored_dict(cls, data: dict[str, Any]) -> "ScoredPlace":
        """Construct a ScoredPlace from a scored dict returned by score_places."""
        geometry = data.get("geometry") or {}
        location = geometry.get("location") or {}
        opening_hours = data.get("opening_hours") or {}
        distance_meters = geometry.get("distance_meters")
        distance_km = data.get("distance_km") or (
            round(distance_meters / 1000, 2) if distance_meters else 0.0
        )

        return cls(
            place_id=data.get("place_id", ""),
            name=data.get("name", ""),
            rating=float(data.get("rating") or 0.0),
            distance_km=float(distance_km),
            address=data.get("vicinity") or data.get("formatted_address", ""),
            latitude=location.get("lat"),
            longitude=location.get("lng"),
            open_now=bool(opening_hours.get("open_now")),
            price_level=data.get("price_level"),
            types=data.get("types") or [],
            photo_refs=[
                p.get("photo_reference", "")
                for p in (data.get("photos") or [])
            ],
            cuisine_type=data.get("cuisine_type"),
            distance_meters=distance_meters,
            next_page_token=data.get("_next_page_token"),
            score=float(data.get("score") or 0.0),
        )
