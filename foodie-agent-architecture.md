# Kiến trúc kỹ thuật — Foodie Agent Chatbot

## Tổng quan

Foodie Agent là ReAct-based chatbot tìm quán ăn qua Google Places API. Tài liệu này mô tả kiến trúc backend, database và external APIs — không bao gồm Frontend và Deploy.

**Tech stack cốt lõi:** Python · FastAPI · LangGraph · MongoDB · Google Maps Platform

---

## 1. API Gateway

**Runtime:** Python FastAPI + Uvicorn

### Nhiệm vụ

- Xác thực request qua JWT (thư viện `python-jose`)
- Duy trì kết nối WebSocket để stream phản hồi realtime
- Rate limiting chống spam API call (`slowapi`)
- Ghi log toàn bộ request/response để debug guardrail

### Endpoint chính

| Endpoint                 | Phương thức | Mô tả                                         |
| ------------------------ | ----------- | --------------------------------------------- |
| `/ws/chat`               | WebSocket   | Luồng chat chính với agent, stream từng token |
| `/api/session`           | POST        | Tạo session mới, trả JWT                      |
| `/api/history/{user_id}` | GET         | Lấy lịch sử chọn quán                         |
| `/api/selection`         | POST        | Lưu quán user đã chọn                         |

### Cấu trúc thư mục

```
app/
├── main.py               # FastAPI app, router mount
├── api/
│   ├── chat.py           # WebSocket endpoint
│   ├── session.py        # Auth endpoints
│   └── history.py        # History endpoints
├── agent/                # ReAct Agent (xem mục 2)
├── tools/                # Tool definitions (xem mục 3)
├── db/                   # MongoDB models & queries (xem mục 4)
├── services/             # Google API clients (xem mục 5)
└── core/
    ├── config.py         # Env vars (pydantic-settings)
    ├── auth.py           # JWT logic
    └── guardrail.py      # Guardrail layer (xem mục 2.3)
```

### WebSocket flow

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

---

## 2. ReAct Agent Core

**Stack:** LangGraph (Python) — quản lý vòng lặp Thought → Action → Observation

**LLM:** Claude Sonnet 3.7 hoặc GPT-4o qua LiteLLM (dễ switch provider)

### 2.1 Vòng lặp ReAct

```
User input
    │
    ▼
[Thought]     LLM phân tích intent, quyết định tool cần gọi
    │
    ▼
[Action]      Gọi tool (LocationTool / GoogleSearchTool / MemoryTool / ScoringTool)
    │
    ▼
[Observation] Nhận kết quả từ tool
    │
    ├── Chưa đủ thông tin → quay lại [Thought]
    │
    └── Đủ → Trả Top 5 quán về user
```

### 2.2 System prompt mẫu

```
You are a Foodie Agent. Your goal is to find the top 5 restaurants.

Tools available:
- get_user_location(user_id): Get lat/lng from GPS or mock data
- search_google_places(location, keyword, sort_by, radius): Query Places API
- calculate_scores(places, weight_quality, weight_distance): Score & rank
- save_user_selection(user_id, place_id): Save to history

Rules:
1. If location is missing, ASK the user for their address.
2. Always check open_now before recommending.
3. Present 5 options with: Name, Rating, Distance, Why you might like it.
4. If user dislikes all 5, trigger expand_search (increase radius or change keyword).
5. After 3 consecutive rejections, stop calling API and ask deep clarification.
```

### 2.3 Guardrail Layer

File `core/guardrail.py` — chạy sau mỗi vòng lặp, kiểm tra các điều kiện:

| Guardrail              | Điều kiện kích hoạt                        | Hành động                                                 |
| ---------------------- | ------------------------------------------ | --------------------------------------------------------- |
| **Zero Result**        | Places API trả `ZERO_RESULTS`              | Thông báo, đề xuất mở rộng bán kính hoặc đổi keyword      |
| **Max Retries**        | User từ chối ≥ 3 lần (15 quán đã hiển thị) | Dừng gọi API, chuyển sang hỏi sâu (không gian, ngân sách) |
| **Ambiguous Location** | Geocoding confidence score < 0.7           | Bắt buộc user xác nhận tọa độ trước khi tìm kiếm          |
| **Midnight Filter**    | Giờ hiện tại 22:00–05:00                   | Ưu tiên `open_now: true`, cảnh báo nếu < 5 quán đang mở   |
| **Anti-hallucination** | Agent tự bịa tên quán                      | Mọi quán phải có `place_id` hợp lệ từ Places API          |

---

## 3. Tools

Mỗi tool là một Python class kế thừa `BaseTool` của LangChain.

### 3.1 LocationTool

**Nhiệm vụ:** Lấy tọa độ `lat/lng` của user.

Luồng xử lý:

1. Thử đọc GPS từ request header (`X-User-Lat`, `X-User-Lng`)
2. Nếu không có → gọi Geocoding API với địa chỉ text user nhập
3. Nếu Geocoding thất bại → tra cứu mock data theo `user_id`

**Mock data — 10 users mẫu:**

```python
# db/mock_data.py
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
```

---

### 3.2 GoogleSearchTool

**Nhiệm vụ:** Truy vấn Google Places API, áp dụng filter, trả danh sách quán thô.

```python
# tools/google_search_tool.py
class GoogleSearchTool(BaseTool):
    name = "search_google_places"

    def _run(self, location: LatLng, keyword: str,
             sort_by: str = "prominence",   # hoặc "distance"
             radius: int = 2000,
             open_now: bool = True,
             next_page_token: str = None) -> list[Place]:

        params = {
            "location":  f"{location.lat},{location.lng}",
            "radius":    radius,
            "keyword":   keyword,
            "opennow":   open_now,
            "rankby":    sort_by,
            "pagetoken": next_page_token,
            "key":       settings.GOOGLE_PLACES_API_KEY,
        }
        response = requests.get(PLACES_NEARBY_URL, params=params)
        return self._parse(response.json())
```

**Chiến lược sort theo preference:**

| Preference user | `sort_by`    | Ghi chú                               |
| --------------- | ------------ | ------------------------------------- |
| Gần nhất        | `distance`   | Bỏ `radius`, bắt buộc theo Places API |
| Ngon nhất       | `prominence` | Radius mặc định 2000m                 |
| Cân bằng        | `prominence` | Kết hợp với ScoringTool sau           |

---

### 3.3 ScoringTool

**Nhiệm vụ:** Tính điểm tổng hợp và xếp hạng Top 5.

**Công thức:**

```
Score = (Rating × W_quality) + (1 / Distance_km × W_distance)
```

Trọng số mặc định: `W_quality = 0.6`, `W_distance = 0.4`

Điều chỉnh tự động theo ngữ cảnh:

- User nói "đang rất đói" → `W_distance = 0.8`
- User nói "muốn ăn ngon" → `W_quality = 0.8`

```python
# tools/scoring_tool.py
class ScoringTool(BaseTool):
    name = "calculate_scores"

    def _run(self, places: list[Place],
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
# tools/memory_tool.py
class MemoryTool(BaseTool):
    name = "memory_tool"

    def get_preference(self, user_id: str) -> UserPreference:
        return db.users.find_one({"user_id": user_id}, {"preference": 1})

    def save_selection(self, user_id: str, place: Place) -> None:
        db.selections.insert_one({
            "user_id":     user_id,
            "place_id":    place.place_id,
            "name":        place.name,
            "cuisine":     place.cuisine_type,
            "selected_at": datetime.utcnow(),
        })
        self._update_preference(user_id, place.cuisine_type)

    def get_shown_places(self, session_id: str) -> list[str]:
        """Lấy place_id đã hiển thị để tránh trùng khi mở rộng tìm kiếm."""
        return db.sessions.find_one({"session_id": session_id})["shown_place_ids"]
```

---

## 4. Database — MongoDB

### Collections

**`users`** — thông tin user và preference tích lũy

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

**`sessions`** — trạng thái từng phiên chat

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

**`selections`** — lịch sử quán đã chọn (dùng để cá nhân hóa về sau)

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

## 5. External APIs

### 5.1 Google Places — Nearby Search

**Endpoint:** `GET https://maps.googleapis.com/maps/api/place/nearbysearch/json`

| Param       | Giá trị                   | Ghi chú                                       |
| ----------- | ------------------------- | --------------------------------------------- |
| `location`  | `lat,lng`                 | Tọa độ user                                   |
| `radius`    | `2000`                    | Đơn vị mét. Bỏ qua nếu dùng `rankby=distance` |
| `keyword`   | `"phở"`, `"cơm tấm"`      | Agent tự sinh từ intent                       |
| `opennow`   | `true`                    | Luôn bật, trừ khi Guardrail midnight override |
| `rankby`    | `prominence` / `distance` | Theo preference user                          |
| `pagetoken` | token từ response cũ      | Dùng khi user nhấn "Tìm thêm"                 |

**Xử lý `next_page_token`:** Lưu vào session sau mỗi lần gọi, dùng lại khi mở rộng tìm kiếm để tránh trả về quán trùng.

---

### 5.2 Google Geocoding — Chuyển địa chỉ text → tọa độ

**Endpoint:** `GET https://maps.googleapis.com/maps/api/geocode/json`

## Xử lý địa chỉ mơ hồ (edge case "Phố Huế"):

### 5.3 Google Distance Matrix — Khoảng cách thực tế

**Endpoint:** `GET https://maps.googleapis.com/maps/api/distancematrix/json`

Dùng để tính `distance_km` chính xác cho ScoringTool thay vì công thức Haversine.

## 6. Edge Cases — Xử lý kỹ thuật

| Edge Case      | Phát hiện                                | Xử lý                                           |
| -------------- | ---------------------------------------- | ----------------------------------------------- |
| GPS bị từ chối | Header lat/lng rỗng                      | Hỏi địa chỉ → Geocoding → fallback mock data    |
| ZERO_RESULTS   | `status == "ZERO_RESULTS"`               | Tăng radius 2km → 5km → 10km, thử đổi keyword   |
| Quán đóng cửa  | `open_now = false`                       | Filter trước khi rank, cảnh báo nếu < 5 quán mở |
| Địa chỉ mơ hồ  | `ambiguous = true` từ Geocoding          | Liệt kê candidates, chờ user xác nhận           |
| Picky user     | `rejection_count >= 3`                   | Dừng gọi API, hỏi không gian + ngân sách        |
| Trùng quán     | `place_id` đã có trong `shown_place_ids` | Dùng `next_page_token` hoặc tăng radius         |

---

## 7. Dependencies

---

## 8. Coding Conventions & Best Practices

### 8.1 Code Style

**Tool:** `ruff` + `black` + `isort`

**Pre-commit hooks (`pre-commit-config.yaml`):**

### 8.2 Naming Conventions

| Loại            | Convention       | Ví dụ                                   |
| --------------- | ---------------- | --------------------------------------- |
| Class           | PascalCase       | `GoogleSearchTool`, `UserPreference`    |
| Function/Method | snake_case       | `calculate_scores`, `get_user_location` |
| Variable        | snake_case       | `user_id`, `place_id`, `session_id`     |
| Constant        | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_RADIUS`         |
| Private method  | `_snake_case`    | `_parse_response`, `_build_headers`     |
| Async function  | `async_<verb>`   | `async_get_places`, `async_save_user`   |
| Environment var | UPPER_SNAKE_CASE | `GOOGLE_PLACES_API_KEY`                 |

### 8.3 Type Annotations

**Bắt buộc** cho tất cả function parameters, return values, và class attributes.

### 8.4 Docstring Format

Dùng Google style docstrings:

### 8.5 Error Handling

### 8.6 Logging Standards

### 8.7 Import Order (isort)

### 8.8 Async/Await Best Practices

### 8.9 Testing Conventions

---

## 9. Docker Configuration

### 9.1 Dockerfile

### 9.2 Multi-stage Build (Production)

### 9.3 docker-compose.yml

### 9.4 docker-compose.prod.yml

### 9.5 .dockerignore

### 9.6 Health Check Endpoint

### 9.7 Build & Run Commands
