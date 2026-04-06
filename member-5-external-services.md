# Backend-5: External Services

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
├── db/                   # MongoDB models & queries
├── services/             # ⭐ Google API clients
└── core/
    ├── config.py         # Env vars
    ├── auth.py           # JWT logic
    └── guardrail.py      # Guardrail layer
```

---

## Feature: External Services

**HTTP Client:** `httpx` (async)

---

### 5.1 Google Places — Nearby Search

**Endpoint:** `GET https://maps.googleapis.com/maps/api/place/nearbysearch/json`

| Param | Giá trị | Ghi chú |
|-------|---------|---------|
| `location` | `lat,lng` | Tọa độ user |
| `radius` | `2000` | Đơn vị mét. Bỏ qua nếu dùng `rankby=distance` |
| `keyword` | `"phở"`, `"cơm tấm"` | Agent tự sinh từ intent |
| `opennow` | `true` | Luôn bật, trừ khi Guardrail midnight override |
| `rankby` | `prominence` / `distance` | Theo preference user |
| `pagetoken` | token từ response cũ | Dùng khi user nhấn "Tìm thêm" |

**Xử lý `next_page_token`:** Lưu vào session sau mỗi lần gọi, dùng lại khi mở rộng tìm kiếm.

```python
# app/services/google_places.py
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

class PlacesClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)

    async def nearby_search(
        self,
        location: LatLng,
        keyword: str,
        sort_by: str = "prominence",
        radius: int = 2000,
        open_now: bool = True,
        next_page_token: str = None
    ) -> list[Place]:
        params = {
            "location": f"{location.lat},{location.lng}",
            "keyword": keyword,
            "opennow": open_now,
            "key": self.api_key,
        }

        if sort_by == "distance":
            params["rankby"] = "distance"
        else:
            params["radius"] = radius

        if next_page_token:
            params["pagetoken"] = next_page_token

        response = await self.client.get(PLACES_NEARBY_URL, params=params)
        return self._parse_response(response.json())

    def _parse_response(self, data: dict) -> list[Place]:
        if data.get("status") == "ZERO_RESULTS":
            return []

        places = []
        for result in data.get("results", []):
            location = result["geometry"]["location"]
            places.append(Place(
                place_id=result["place_id"],
                name=result["name"],
                rating=result.get("rating", 0.0),
                distance_km=0.0,  # Will be calculated by distance_matrix
                address=result.get("vicinity", ""),
                open_now=result.get("opening_hours", {}).get("open_now", False),
            ))

        return places
```

---

### 5.2 Google Geocoding — Chuyển địa chỉ text → tọa độ

**Endpoint:** `GET https://maps.googleapis.com/maps/api/geocode/json`

```python
GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

class GeocodingClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)

    async def geocode(self, address: str) -> LatLng:
        params = {
            "address": address,
            "key": self.api_key,
        }

        response = await self.client.get(GEOCODING_URL, params=params)
        data = response.json()

        if data.get("status") == "OK":
            result = data["results"][0]
            location = result["geometry"]["location"]
            confidence = result.get("confidence", 1.0)
            return GeocodingResult(
                lat_lng=LatLng(lat=location["lat"], lng=location["lng"]),
                confidence=confidence,
                ambiguous=len(data["results"]) > 1
            )

        raise GeocodingError(f"Geocoding failed: {data.get('status')}")
```

**Edge case: Địa chỉ mơ hồ (VD: "Phố Huế")**

```python
@dataclass
class GeocodingResult:
    lat_lng: LatLng
    confidence: float  # 0.0 - 1.0
    ambiguous: bool     # True if multiple candidates

# If ambiguous=True → return list of candidates cho user xác nhận
# If confidence < 0.7 → Guardrail Ambiguous Location kích hoạt
```

---

### 5.3 Google Distance Matrix — Khoảng cách thực tế

**Endpoint:** `GET https://maps.googleapis.com/maps/api/distancematrix/json`

Dùng để tính `distance_km` chính xác cho ScoringTool thay vì công thức Haversine.

```python
DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

class DistanceMatrixClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_distances(
        self,
        origin: LatLng,
        destinations: list[str]  # list of place_ids
    ) -> dict[str, float]:  # place_id -> distance_km
        params = {
            "origins": f"{origin.lat},{origin.lng}",
            "destinations": "place_id:" + "|place_id:".join(destinations),
            "key": self.api_key,
        }

        response = await self.client.get(DISTANCE_MATRIX_URL, params=params)
        data = response.json()

        distances = {}
        for row in data.get("rows", []):
            for element in row.get("elements", []):
                if element["status"] == "OK":
                    place_id = destinations[len(distances)]
                    distances[place_id] = element["distance"]["value"] / 1000

        return distances
```

---

### 5.4 Shared Client with Retry Logic

```python
# app/services/client.py
class GoogleAPIClient:
    def __init__(self, api_key: str, max_retries: int = 3):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=100)
        )
        self.places = PlacesClient(api_key)
        self.geocoding = GeocodingClient(api_key)
        self.distance = DistanceMatrixClient(api_key)

    async def close(self):
        await self.client.aclose()
```

---

## Dependencies

- **Used by:** `app/tools/` (GoogleSearchTool, LocationTool gọi services)
- **External:** `httpx`, Google Maps API key

---

## Files to Create

```
app/services/
├── __init__.py
├── client.py          # Shared async client
├── google_places.py  # ⭐ Places Nearby Search
├── geocoding.py      # ⭐ Address to LatLng
└── distance_matrix.py # ⭐ Real distance calculation
```

---

## Checklist

- [ ] `app/services/client.py` - Shared httpx client với retry
- [ ] `app/services/google_places.py` - Places Nearby Search
- [ ] `app/services/geocoding.py` - Address → LatLng
- [ ] `app/services/distance_matrix.py` - Real distance
- [ ] Error handling (rate limit, timeout, invalid API key)
- [ ] Unit tests với mock responses
