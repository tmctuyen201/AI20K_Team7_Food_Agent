# Backend-3: Tools

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
├── tools/                # ⭐ Tool definitions
├── db/                   # MongoDB models & queries
├── services/             # Google API clients
└── core/
    ├── config.py         # Env vars
    ├── auth.py           # JWT logic
    └── guardrail.py      # Guardrail layer
```

---

## Feature: Tools

Mỗi tool là một Python class kế thừa `BaseTool` của LangChain.

### 4 Tools cần implement

---

### 3.1 LocationTool

**Nhiệm vụ:** Lấy tọa độ `lat/lng` của user.

**Luồng xử lý:**

1. Thử đọc GPS từ request header (`X-User-Lat`, `X-User-Lng`)
2. Nếu không có → gọi Geocoding API với địa chỉ text user nhập
3. Nếu Geocoding thất bại → tra cứu mock data theo `user_id`

```python
class LocationTool(BaseTool):
    name = "get_user_location"
    description = "Get lat/lng coordinates for a user"

    def _run(self, user_id: str, address: str = None) -> LatLng:
        # 1. Check headers
        lat = request.headers.get("X-User-Lat")
        lng = request.headers.get("X-User-Lng")
        if lat and lng:
            return LatLng(lat=float(lat), lng=float(lng))

        # 2. Geocoding if address provided
        if address:
            return geocoding_service.geocode(address)

        # 3. Fallback to mock data
        return mock_data.get_location(user_id)
```

**Mock data (từ db/mock_data.py):**

```python
MOCK_USERS = [
    {"user_id": "u01", "name": "Minh", "lat": 21.0285, "lng": 105.8542, "city": "Hà Nội - Hoàn Kiếm"},
    {"user_id": "u02", "name": "Linh", "lat": 10.7769, "lng": 106.7009, "city": "TP.HCM - Quận 1"},
    {"user_id": "u03", "name": "Hùng", "lat": 16.0544, "lng": 108.2022, "city": "Đà Nẵng - Hải Châu"},
    # ... 10 users total
]
```

---

### 3.2 GoogleSearchTool

**Nhiệm vụ:** Truy vấn Google Places API, trả danh sách quán thô.

```python
class GoogleSearchTool(BaseTool):
    name = "search_google_places"
    description = "Search restaurants near a location"

    def _run(self,
             location: LatLng,
             keyword: str,
             sort_by: str = "prominence",
             radius: int = 2000,
             open_now: bool = True,
             next_page_token: str = None) -> list[Place]:

        params = {
            "location": f"{location.lat},{location.lng}",
            "radius": radius,
            "keyword": keyword,
            "opennow": open_now,
            "rankby": sort_by,
            "pagetoken": next_page_token,
        }
        return places_client.nearby_search(params)
```

**Sort strategy:**

| Preference | `sort_by` | Ghi chú |
|------------|-----------|---------|
| Gần nhất | `distance` | Bỏ `radius`, bắt buộc theo Places API |
| Ngon nhất | `prominence` | Radius mặc định 2000m |
| Cân bằng | `prominence` | Kết hợp với ScoringTool |

---

### 3.3 ScoringTool

**Nhiệm vụ:** Tính điểm tổng hợp và xếp hạng Top 5.

**Công thức:**

```
Score = (Rating × W_quality) + (1 / Distance_km × W_distance)
```

**Trọng số mặc định:** `W_quality = 0.6`, `W_distance = 0.4`

**Điều chỉnh tự động theo ngữ cảnh:**

- User nói "đang rất đói" → `W_distance = 0.8`
- User nói "muốn ăn ngon" → `W_quality = 0.8`

```python
class ScoringTool(BaseTool):
    name = "calculate_scores"
    description = "Score and rank restaurants"

    def _run(self,
             places: list[Place],
             w_quality: float = 0.6,
             w_distance: float = 0.4) -> list[ScoredPlace]:

        for place in places:
            place.score = (
                place.rating * w_quality +
                (1 / max(place.distance_km, 0.1)) * w_distance
            )
        return sorted(places, key=lambda p: p.score, reverse=True)[:5]
```

---

### 3.4 MemoryTool

**Nhiệm vụ:** Đọc/ghi preference và lịch sử của user vào MongoDB.

```python
class MemoryTool(BaseTool):
    name = "memory_tool"
    description = "Read/write user preferences and history"

    def get_preference(self, user_id: str) -> UserPreference:
        return db.users.find_one({"user_id": user_id}, {"preference": 1})

    def save_selection(self, user_id: str, place: Place) -> None:
        db.selections.insert_one({
            "user_id": user_id,
            "place_id": place.place_id,
            "name": place.name,
            "cuisine": place.cuisine_type,
            "selected_at": datetime.utcnow(),
        })
        self._update_preference(user_id, place.cuisine_type)

    def get_shown_places(self, session_id: str) -> list[str]:
        """Lấy place_id đã hiển thị để tránh trùng."""
        return db.sessions.find_one({"session_id": session_id})["shown_place_ids"]
```

---

## Dependencies

- **Uses:** `app/db/` (MongoDB queries)
- **Uses:** `app/services/` (Google API clients)
- **Used by:** `app/agent/nodes.py` (agent calls tools)

---

## Files to Create

```
app/tools/
├── __init__.py
├── base.py              # BaseTool abstract class
├── location_tool.py     # ⭐
├── google_search_tool.py # ⭐
├── scoring_tool.py      # ⭐
├── memory_tool.py       # ⭐
└── registry.py         # Tool registry for agent
```

---

## Checklist

- [ ] `app/tools/base.py` - BaseTool abstract class
- [ ] `app/tools/location_tool.py` - Get user location
- [ ] `app/tools/google_search_tool.py` - Search Places API
- [ ] `app/tools/scoring_tool.py` - Score & rank
- [ ] `app/tools/memory_tool.py` - Read/write user data
- [ ] `app/tools/registry.py` - Register all tools
- [ ] Unit tests cho mỗi tool
