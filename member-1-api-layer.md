# Backend-1: API Layer

## Architecture Overview

Foodie Agent là ReAct-based chatbot tìm quán ăn qua Google Places API.

**Tech stack:** Python · FastAPI · LangGraph · MongoDB · Google Maps Platform

### Project Structure

```
app/
├── main.py               # FastAPI app, router mount
├── api/
│   ├── chat.py           # ⭐ WebSocket endpoint
│   ├── session.py        # ⭐ Auth endpoints
│   └── history.py        # ⭐ History endpoints
├── agent/                # ReAct Agent
├── tools/                # Tool definitions
├── db/                   # MongoDB models & queries
├── services/             # Google API clients
└── core/
    ├── config.py         # Env vars
    ├── auth.py           # ⭐ JWT logic
    └── guardrail.py      # Guardrail layer
```

---

## Feature: API Layer

### Nhiệm vụ

1. **Xác thực request** qua JWT (thư viện `python-jose`)
2. **Duy trì WebSocket** để stream phản hồi realtime
3. **Rate limiting** chống spam API call (`slowapi`)
4. **Ghi log** toàn bộ request/response để debug guardrail

### Endpoints cần implement

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/ws/chat` | WebSocket | Luồng chat chính, stream từng token |
| `/api/session` | POST | Tạo session mới, trả JWT |
| `/api/history/{user_id}` | GET | Lấy lịch sử chọn quán |
| `/api/selection` | POST | Lưu quán user đã chọn |

### WebSocket Flow

```
Client kết nối /ws/chat
    │
    ├── Gửi message (JSON): { "text": "...", "user_id": "..." }
    │
    ├── Agent xử lý (stream từng chunk)
    │       └── server gửi: { "type": "token", "data": "..." }
    │
    └── Kết thúc: { "type": "done", "data": { "places": [...] } }
```

### JWT Flow

```python
# 1. Tạo token khi tạo session
def create_session_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return create_access_token(payload)

# 2. Verify token trong mỗi request
def verify_token(token: str) -> dict:
    return decode_token(token, settings.JWT_SECRET)
```

---

## Shared Models (Interface với các track khác)

```python
# app/db/models.py - Dùng chung, viết bởi Database track
class Place(BaseModel):
    place_id: str
    name: str
    rating: float
    distance_km: float
    address: str
    open_now: bool

class ChatMessage(BaseModel):
    text: str
    user_id: str

class AgentResponse(BaseModel):
    type: Literal["token", "done"]
    data: Union[str, list[Place]]
```

---

## Dependencies

- **Uses:** `app/db/models.py` (read only)
- **Called by:** `app/agent/graph.py`
- **External:** `python-jose`, `slowapi`, `uvicorn`

---

## Checklist

- [ ] `app/core/config.py` - Pydantic settings từ env
- [ ] `app/core/auth.py` - JWT create/verify
- [ ] `app/api/session.py` - POST /api/session
- [ ] `app/api/history.py` - GET /api/history, POST /api/selection
- [ ] `app/api/chat.py` - WebSocket /ws/chat
- [ ] Rate limiting middleware
- [ ] Logging middleware cho request/response
- [ ] Unit tests cho auth functions
