# Backend-4: Database

## Architecture Overview

Foodie Agent là ReAct-based chatbot tìm quán ăn qua Google Places API.

**Tech stack:** Python · FastAPI · LangGraph · MongoDB · Google Maps Platform

### Project Structure

```
app/
├── main.py               # FastAPI app, router mount
├── api/
│   ├── chat.py           # WebSocket endpoint
│   ├── session.py        # Auth endpoints
│   └── history.py        # History endpoints
├── agent/                # ReAct Agent
├── tools/                # Tool definitions
├── db/                   # ⭐ MongoDB models & queries
├── services/             # Google API clients
└── core/
    ├── config.py         # Env vars
    ├── auth.py           # JWT logic
    └── guardrail.py      # Guardrail layer
```

---

## Feature: Database

**Driver:** Motor (async MongoDB driver)

### Collections

---

### `users` — Thông tin user và preference tích lũy

```json
{
  "_id": "ObjectId",
  "user_id": "u01",
  "name": "Minh",
  "default_location": { "lat": 21.0285, "lng": 105.8542 },
  "preference": {
    "favorite_cuisines": ["phở", "bún bò"],
    "avoid_cuisines": [],
    "price_range": "mid",
    "preferred_ambiance": "vỉa hè"
  },
  "created_at": "ISODate"
}
```

---

### `sessions` — Trạng thái từng phiên chat

```json
{
  "_id": "ObjectId",
  "session_id": "sess_abc123",
  "user_id": "u01",
  "location": { "lat": 21.0285, "lng": 105.8542 },
  "shown_place_ids": ["ChIJ...", "ChIJ..."],
  "rejection_count": 1,
  "last_keyword": "phở",
  "last_radius": 2000,
  "next_page_token": "token_xyz",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

---

### `selections` — Lịch sử quán đã chọn

```json
{
  "_id": "ObjectId",
  "user_id": "u01",
  "place_id": "ChIJ...",
  "name": "Phở Thìn",
  "cuisine_type": "phở",
  "rating": 4.5,
  "selected_at": "ISODate"
}
```

---

## Files to Create

### `app/db/connection.py` — MongoDB async connection

```python
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

class Database:
    client: AsyncIOMotorClient = None

db = Database()

async def connect_db():
    db.client = AsyncIOMotorClient(settings.MONGODB_URI)
    # Create indexes
    db.client.foodie.users.create_index("user_id", unique=True)
    db.client.foodie.sessions.create_index("session_id", unique=True)
    db.client.foodie.selections.create_index([("user_id", 1), ("selected_at", -1)])

async def close_db():
    db.client.close()

def get_db() -> AsyncIOMotorDatabase:
    return db.client.foodie
```

---

### `app/db/models.py` — Pydantic models (SHARED across all tracks)

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LatLng(BaseModel):
    lat: float
    lng: float

class Place(BaseModel):
    place_id: str
    name: str
    rating: float
    distance_km: float
    address: str
    open_now: bool
    cuisine_type: Optional[str] = None

class ScoredPlace(Place):
    score: float

class UserPreference(BaseModel):
    favorite_cuisines: list[str] = []
    avoid_cuisines: list[str] = []
    price_range: str = "mid"
    preferred_ambiance: Optional[str] = None

class User(BaseModel):
    user_id: str
    name: str
    default_location: LatLng
    preference: UserPreference = UserPreference()
    created_at: datetime

class Session(BaseModel):
    session_id: str
    user_id: str
    location: LatLng
    shown_place_ids: list[str] = []
    rejection_count: int = 0
    last_keyword: Optional[str] = None
    last_radius: int = 2000
    next_page_token: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class Selection(BaseModel):
    user_id: str
    place_id: str
    name: str
    cuisine_type: Optional[str] = None
    rating: float
    selected_at: datetime

class ChatMessage(BaseModel):
    text: str
    user_id: str

class AgentResponse(BaseModel):
    type: Literal["token", "done"]
    data: Union[str, list[Place]]
```

---

### `app/db/queries.py` — CRUD functions

```python
from typing import Optional
from datetime import datetime

async def get_user(user_id: str) -> Optional[User]:
    doc = await get_db().users.find_one({"user_id": user_id})
    return User(**doc) if doc else None

async def create_user(user: User) -> None:
    await get_db().users.insert_one(user.model_dump())

async def update_user_preference(user_id: str, preference: UserPreference) -> None:
    await get_db().users.update_one(
        {"user_id": user_id},
        {"$set": {"preference": preference.model_dump()}}
    )

async def create_session(session: Session) -> None:
    await get_db().sessions.insert_one(session.model_dump())

async def update_session(session_id: str, **kwargs) -> None:
    kwargs["updated_at"] = datetime.utcnow()
    await get_db().sessions.update_one(
        {"session_id": session_id},
        {"$set": kwargs}
    )

async def get_session(session_id: str) -> Optional[Session]:
    doc = await get_db().sessions.find_one({"session_id": session_id})
    return Session(**doc) if doc else None

async def save_selection(selection: Selection) -> None:
    await get_db().selections.insert_one(selection.model_dump())

async def get_user_selections(user_id: str, limit: int = 20) -> list[Selection]:
    cursor = get_db().selections.find(
        {"user_id": user_id}
    ).sort("selected_at", -1).limit(limit)
    return [Selection(**doc) async for doc in cursor]
```

---

### `app/db/mock_data.py` — 10 sample users

```python
MOCK_USERS = [
    {"user_id": "u01", "name": "Minh", "lat": 21.0285, "lng": 105.8542, "city": "Hà Nội - Hoàn Kiếm"},
    {"user_id": "u02", "name": "Linh", "lat": 10.7769, "lng": 106.7009, "city": "TP.HCM - Quận 1"},
    {"user_id": "u03", "name": "Hùng", "lat": 16.0544, "lng": 108.2022, "city": "Đà Nẵng - Hải Châu"},
    {"user_id": "u04", "name": "Lan",  "lat": 10.0341, "lng": 105.7852, "city": "Cần Thơ - Ninh Kiều"},
    {"user_id": "u05", "name": "Nam",  "lat": 20.8449, "lng": 106.6881, "city": "Hải Phòng - Lê Chân"},
    {"user_id": "u06", "name": "Mai",  "lat": 10.9574, "lng": 106.8426, "city": "TP.HCM - Thủ Đức"},
    {"user_id": "u07", "name": "Tuấn", "lat": 21.5944, "lng": 105.8412, "city": "Vĩnh Phúc - Vĩnh Yên"},
    {"user_id": "u08", "name": "Hoa",  "lat": 12.2388, "lng": 109.1967, "city": "Nha Trang - Vĩnh Hải"},
    {"user_id": "u09", "name": "Bình", "lat": 13.7830, "lng": 109.2194, "city": "Quy Nhơn - Nhơn Bình"},
    {"user_id": "u10", "name": "Dung", "lat": 11.9465, "lng": 108.4419, "city": "Đà Lạt - Phường 1"},
]

def get_mock_location(user_id: str) -> LatLng:
    user = next((u for u in MOCK_USERS if u["user_id"] == user_id), MOCK_USERS[0])
    return LatLng(lat=user["lat"], lng=user["lng"])
```

---

## Dependencies

- **Used by:** All other tracks (shared models)
- **External:** `motor` (async MongoDB driver)

---

## Checklist

- [ ] `app/db/connection.py` - Async MongoDB connection
- [ ] `app/db/models.py` - All Pydantic models (IMPORTANT: shared across tracks)
- [ ] `app/db/queries.py` - CRUD operations
- [ ] `app/db/mock_data.py` - 10 sample users
- [ ] `app/db/__init__.py` - Export models and functions
- [ ] Unit tests cho queries
