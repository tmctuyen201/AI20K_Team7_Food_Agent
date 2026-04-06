# Hướng dẫn phát triển: `get_user_location` Feature

## Mục lục

1. [Tổng quan Feature](#1-tổng-quan-feature)
2. [Business Logic Flow](#2-business-logic-flow)
3. [Step-by-step Development](#3-step-by-step-development)
4. [Error Handling Cases](#4-error-handling-cases)
5. [Unit Testing](#5-unit-testing)
6. [Code Implementation](#6-code-implementation)

---

## 1. Tổng quan Feature

### Mục tiêu
Lấy tọa độ `lat/lng` của user từ nhiều nguồn với fallback hierarchy.

### Nguồn dữ liệu (theo thứ tự ưu tiên)

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | GPS Headers | `X-User-Lat`, `X-User-Lng` từ request |
| 2 | Geocoding API | Chuyển địa chỉ text → tọa độ |
| 3 | Mock Data | Fallback cuối cùng theo `user_id` |

### Edge Cases cần xử lý

| Case | Input | Expected Output |
|------|-------|-----------------|
| Happy path - GPS | Valid headers | Return LatLng from headers |
| Happy path - Address | No headers, address provided | Return LatLng from Geocoding |
| Happy path - Mock | No headers, no address | Return LatLng from mock data |
| Invalid GPS | Headers present but invalid | Fallback to next source |
| Geocoding fail | Address provided but API fails | Fallback to mock data |
| Unknown user_id | Mock lookup fails | Return default location |
| Missing everything | No headers, no address, unknown user | Raise exception |

---

## 2. Business Logic Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    get_user_location                         │
│  Input: user_id, address (optional)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Check Headers  │
                    │ X-User-Lat/Lng   │
                    └─────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │ Valid          │ Invalid/Missing│
              ▼                               ▼
    ┌─────────────────┐              ┌─────────────────┐
    │  Return LatLng   │              │ Check Address   │
    │  from headers    │              │ Provided?       │
    └─────────────────┘              └─────────────────┘
                                              │
                              ┌───────────────┼───────────────┐
                              │ Yes           │ No             │
                              ▼                               ▼
                    ┌─────────────────┐              ┌─────────────────┐
                    │  Call Geocoding  │              │ Check Mock Data │
                    │  API             │              │ by user_id      │
                    └─────────────────┘              └─────────────────┘
                              │                               │
              ┌───────────────┼───────────────┐               │
              │ Success       │ Fail          │               │
              ▼                               ▼               ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │  Return LatLng   │    │  Check Mock     │    │ Return LatLng   │
    │  from geocoding  │    │  Data           │    │ from mock_data  │
    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 3. Step-by-step Development

### Step 1: Tạo Type Definitions

```python
# app/db/models.py (nếu chưa có)
from pydantic import BaseModel
from typing import Optional
from dataclasses import dataclass

@dataclass
class LatLng:
    lat: float
    lng: float

class LocationResult(BaseModel):
    lat: float
    lng: float
    source: str  # "headers" | "geocoding" | "mock_data"
    confidence: float = 1.0
```

### Step 2: Tạo Mock Data

```python
# app/db/mock_data.py
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

DEFAULT_LOCATION = {"lat": 21.0285, "lng": 105.8542}  # Hà Nội - fallback cuối cùng

def get_mock_location(user_id: str) -> dict:
    """Tìm location từ mock data theo user_id"""
    user = next(
        (u for u in MOCK_USERS if u["user_id"] == user_id),
        DEFAULT_LOCATION
    )
    return {"lat": user["lat"], "lng": user["lng"]}
```

### Step 3: Tạo Geocoding Service

```python
# app/services/geocoding.py
import httpx
from typing import Optional
from app.core.config import settings

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

class GeocodingError(Exception):
    pass

class GeocodingClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GOOGLE_GEOCODING_API_KEY
        self.client = httpx.AsyncClient(timeout=10.0)

    async def geocode(self, address: str) -> dict:
        """Chuyển địa chỉ text thành tọa độ"""
        try:
            params = {
                "address": address,
                "key": self.api_key,
            }
            response = await self.client.get(GEOCODING_URL, params=params)
            data = response.json()

            if data.get("status") == "OK":
                result = data["results"][0]
                location = result["geometry"]["location"]
                return {
                    "lat": location["lat"],
                    "lng": location["lng"],
                    "confidence": 0.8,  # Default confidence
                }
            elif data.get("status") == "ZERO_RESULTS":
                raise GeocodingError(f"No results for address: {address}")
            else:
                raise GeocodingError(f"Geocoding API error: {data.get('status')}")

        except httpx.TimeoutException:
            raise GeocodingError("Geocoding API timeout")
        except httpx.HTTPError as e:
            raise GeocodingError(f"Geocoding HTTP error: {e}")

    async def close(self):
        await self.client.aclose()
```

### Step 4: Implement LocationService (Core Logic)

```python
# app/services/location_service.py
from typing import Optional, Literal
from dataclasses import dataclass
from app.services.geocoding import GeocodingClient, GeocodingError
from app.db.mock_data import get_mock_location, DEFAULT_LOCATION

@dataclass
class LocationResult:
    lat: float
    lng: float
    source: Literal["headers", "geocoding", "mock_data"]
    confidence: float = 1.0

class LocationService:
    def __init__(self):
        self.geocoding_client = GeocodingClient()

    async def get_user_location(
        self,
        user_id: str,
        address: Optional[str] = None,
        headers: Optional[dict] = None
    ) -> LocationResult:
        """
        Lấy location của user với fallback hierarchy:
        1. GPS Headers
        2. Geocoding (nếu có address)
        3. Mock Data (fallback cuối cùng)
        """
        # === Priority 1: GPS Headers ===
        if headers:
            lat_str = headers.get("X-User-Lat") or headers.get("x-user-lat")
            lng_str = headers.get("X-User-Lng") or headers.get("x-user-lng")

            if lat_str and lng_str:
                try:
                    lat = float(lat_str)
                    lng = float(lng_str)

                    # Validate range
                    if -90 <= lat <= 90 and -180 <= lng <= 180:
                        return LocationResult(
                            lat=lat,
                            lng=lng,
                            source="headers",
                            confidence=0.95
                        )
                except ValueError:
                    # Invalid numeric format, continue to next source
                    pass

        # === Priority 2: Geocoding (if address provided) ===
        if address:
            try:
                result = await self.geocoding_client.geocode(address)
                return LocationResult(
                    lat=result["lat"],
                    lng=result["lng"],
                    source="geocoding",
                    confidence=result.get("confidence", 0.8)
                )
            except (GeocodingError, Exception):
                # Geocoding failed, continue to mock data
                pass

        # === Priority 3: Mock Data ===
        mock_location = get_mock_location(user_id)
        return LocationResult(
            lat=mock_location["lat"],
            lng=mock_location["lng"],
            source="mock_data",
            confidence=0.5  # Lower confidence for mock data
        )

    async def close(self):
        await self.geocoding_client.close()
```

### Step 5: Tạo Tool Wrapper (LangChain BaseTool)

```python
# app/tools/location_tool.py
from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from app.services.location_service import LocationService, LocationResult

class GetUserLocationInput(BaseModel):
    user_id: str = Field(description="User ID to identify the user")
    address: Optional[str] = Field(
        default=None,
        description="User's address string (optional)"
    )

class GetUserLocationOutput(BaseModel):
    lat: float
    lng: float
    source: str
    confidence: float

class GetUserLocationTool(BaseTool):
    name = "get_user_location"
    description = """
    Get the geographic coordinates (latitude, longitude) of a user.
    Uses GPS headers first, then geocoding if address provided, then mock data as fallback.

    Input:
    - user_id: The unique identifier of the user (required)
    - address: The user's address as a string (optional)
    """
    args_schema: Type[BaseModel] = GetUserLocationInput
    location_service: LocationService = None

    def __init__(self, location_service: LocationService = None):
        super().__init__()
        self.location_service = location_service or LocationService()

    async def _arun(
        self,
        user_id: str,
        address: Optional[str] = None,
        headers: Optional[dict] = None
    ) -> dict:
        result = await self.location_service.get_user_location(
            user_id=user_id,
            address=address,
            headers=headers
        )
        return {
            "lat": result.lat,
            "lng": result.lng,
            "source": result.source,
            "confidence": result.confidence
        }

    def _run(self, user_id: str, address: Optional[str] = None) -> dict:
        """Sync wrapper - for cases where async is not available"""
        import asyncio
        return asyncio.run(self._arun(user_id, address))
```

---

## 4. Error Handling Cases

### Case 1: GPS Headers có nhưng invalid

```python
# Test: Headers có format sai
headers = {
    "X-User-Lat": "invalid_number",
    "X-User-Lng": "106.7009"
}
# Expected: Fallback sang Geocoding hoặc Mock Data
```

### Case 2: Geocoding API fail

```python
# Test: Address provided nhưng Geocoding timeout/error
# Expected: Fallback sang Mock Data
# Expected: Log warning message
```

### Case 3: Unknown user_id

```python
# Test: user_id không có trong mock data
user_id = "unknown_user_123"
# Expected: Return DEFAULT_LOCATION (Hà Nội)
```

### Case 4: Không có gì cả (trường hợp hiếm)

```python
# Test: Không headers, không address, không user_id hợp lệ
# Expected: Vẫn return DEFAULT_LOCATION thay vì crash
```

---

## 5. Unit Testing

### File: `tests/test_location_service.py`

```python
# tests/test_location_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.location_service import LocationService, LocationResult
from app.services.geocoding import GeocodingError

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def location_service():
    return LocationService()

@pytest.fixture
def valid_headers():
    return {
        "X-User-Lat": "21.0285",
        "X-User-Lng": "105.8542"
    }

@pytest.fixture
def invalid_headers():
    return {
        "X-User-Lat": "not_a_number",
        "X-User-Lng": "also_not_a_number"
    }

@pytest.fixture
def out_of_range_headers():
    return {
        "X-User-Lat": "200.0",  # Invalid: > 90
        "X-User-Lng": "105.8542"
    }

# ============================================================
# TEST: GPS Headers (Priority 1)
# ============================================================

class TestGPSHeaders:
    """Test cases cho Priority 1: GPS Headers"""

    @pytest.mark.asyncio
    async def test_valid_headers_returns_location_from_headers(
        self, location_service, valid_headers
    ):
        """Happy path: Valid GPS headers → return location from headers"""
        result = await location_service.get_user_location(
            user_id="u01",
            address=None,
            headers=valid_headers
        )

        assert result.lat == 21.0285
        assert result.lng == 105.8542
        assert result.source == "headers"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_case_insensitive_headers(
        self, location_service
    ):
        """Headers có thể viết thường hoặc hoa"""
        headers = {
            "x-user-lat": "10.7769",
            "x-user-lng": "106.7009"
        }

        result = await location_service.get_user_location(
            user_id="u01",
            headers=headers
        )

        assert result.lat == 10.7769
        assert result.lng == 106.7009
        assert result.source == "headers"

    @pytest.mark.asyncio
    async def test_invalid_numeric_format_fallback_to_mock(
        self, location_service, invalid_headers
    ):
        """Invalid number format → fallback to mock data"""
        result = await location_service.get_user_location(
            user_id="u02",  # Linh - TP.HCM
            headers=invalid_headers
        )

        # Should fallback to mock data
        assert result.source == "mock_data"
        assert result.lat == 10.7769  # u02's mock location
        assert result.lng == 106.7009

    @pytest.mark.asyncio
    async def test_out_of_range_coordinates_fallback_to_mock(
        self, location_service, out_of_range_headers
    ):
        """Coordinates out of valid range → fallback to mock data"""
        result = await location_service.get_user_location(
            user_id="u01",
            headers=out_of_range_headers
        )

        assert result.source == "mock_data"

    @pytest.mark.asyncio
    async def test_missing_headers_continues_to_next_source(
        self, location_service
    ):
        """Missing headers → try next source (address)"""
        # No headers, no address → should use mock
        result = await location_service.get_user_location(
            user_id="u01"
        )

        assert result.source == "mock_data"

# ============================================================
# TEST: Geocoding (Priority 2)
# ============================================================

class TestGeocoding:
    """Test cases cho Priority 2: Geocoding API"""

    @pytest.mark.asyncio
    async def test_successful_geocoding(
        self, location_service, valid_headers
    ):
        """Valid address → geocoding success"""
        # Override headers to skip to geocoding
        headers = {"X-User-Lat": "", "X-User-Lng": ""}

        with patch.object(
            location_service.geocoding_client,
            'geocode',
            new_callable=AsyncMock,
            return_value={"lat": 16.0544, "lng": 108.2022, "confidence": 0.9}
        ):
            result = await location_service.get_user_location(
                user_id="u01",
                address="Đà Nẵng",
                headers=headers
            )

            assert result.lat == 16.0544
            assert result.lng == 108.2022
            assert result.source == "geocoding"
            assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_geocoding_error_fallback_to_mock(
        self, location_service, valid_headers
    ):
        """Geocoding fails → fallback to mock data"""
        headers = {"X-User-Lat": "", "X-User-Lng": ""}

        with patch.object(
            location_service.geocoding_client,
            'geocode',
            new_callable=AsyncMock,
            side_effect=GeocodingError("API timeout")
        ):
            result = await location_service.get_user_location(
                user_id="u02",  # Linh - TP.HCM
                address="Unknown Address XYZ",
                headers=headers
            )

            # Should fallback to mock
            assert result.source == "mock_data"
            assert result.lat == 10.7769  # u02's mock location

    @pytest.mark.asyncio
    async def test_no_address_skips_geocoding(
        self, location_service, valid_headers
    ):
        """No address → skip geocoding, use mock"""
        headers = {"X-User-Lat": "", "X-User-Lng": ""}

        result = await location_service.get_user_location(
            user_id="u03",  # Hùng - Đà Nẵng
            address=None,
            headers=headers
        )

        # No address, so should use mock
        assert result.source == "mock_data"
        assert result.lat == 16.0544  # u03's mock location

# ============================================================
# TEST: Mock Data (Priority 3)
# ============================================================

class TestMockData:
    """Test cases cho Priority 3: Mock Data fallback"""

    @pytest.mark.asyncio
    async def test_known_user_returns_correct_mock_location(
        self, location_service, valid_headers
    ):
        """Known user_id → return their mock location"""
        headers = {"X-User-Lat": "", "X-User-Lng": ""}

        result = await location_service.get_user_location(
            user_id="u04",  # Lan - Cần Thơ
            headers=headers
        )

        assert result.source == "mock_data"
        assert result.lat == 10.0341
        assert result.lng == 105.7852

    @pytest.mark.asyncio
    async def test_unknown_user_returns_default_location(
        self, location_service, valid_headers
    ):
        """Unknown user_id → return default location (Hà Nội)"""
        headers = {"X-User-Lat": "", "X-User-Lng": ""}

        result = await location_service.get_user_location(
            user_id="unknown_user_123",
            headers=headers
        )

        assert result.source == "mock_data"
        assert result.lat == 21.0285  # DEFAULT: Hà Nội
        assert result.lng == 105.8542
        assert result.confidence == 0.5  # Lower confidence for mock

    @pytest.mark.asyncio
    async def test_all_10_mock_users_work(
        self, location_service, valid_headers
    ):
        """All 10 mock users should return valid locations"""
        headers = {"X-User-Lat": "", "X-User-Lng": ""}
        expected_users = [
            ("u01", 21.0285, 105.8542),
            ("u02", 10.7769, 106.7009),
            ("u03", 16.0544, 108.2022),
            ("u04", 10.0341, 105.7852),
            ("u05", 20.8449, 106.6881),
            ("u06", 10.9574, 106.8426),
            ("u07", 21.5944, 105.8412),
            ("u08", 12.2388, 109.1967),
            ("u09", 13.7830, 109.2194),
            ("u10", 11.9465, 108.4419),
        ]

        for user_id, expected_lat, expected_lng in expected_users:
            result = await location_service.get_user_location(
                user_id=user_id,
                headers=headers
            )
            assert result.lat == expected_lat, f"User {user_id} lat mismatch"
            assert result.lng == expected_lng, f"User {user_id} lng mismatch"

# ============================================================
# TEST: Integration - Full Flow
# ============================================================

class TestFullFlow:
    """Integration tests cho toàn bộ flow"""

    @pytest.mark.asyncio
    async def test_complete_happy_path_with_all_sources(
        self, location_service
    ):
        """Full flow: headers → geocoding → mock"""
        # 1. Valid headers provided
        headers = {"X-User-Lat": "21.0285", "X-User-Lng": "105.8542"}
        result = await location_service.get_user_location(
            user_id="u01",
            address="Some address",
            headers=headers
        )
        assert result.source == "headers"

    @pytest.mark.asyncio
    async def test_headers_priority_over_geocoding(
        self, location_service
    ):
        """Headers should always take priority if valid"""
        headers = {"X-User-Lat": "21.0285", "X-User-Lng": "105.8542"}

        with patch.object(
            location_service.geocoding_client,
            'geocode',
            new_callable=AsyncMock
        ) as mock_geocode:
            result = await location_service.get_user_location(
                user_id="u01",
                address="Any address",
                headers=headers
            )

            # Geocoding should NOT be called when headers are valid
            mock_geocode.assert_not_called()
            assert result.source == "headers"

    @pytest.mark.asyncio
    async def test_empty_headers_dict_treated_as_missing(
        self, location_service
    ):
        """Empty dict headers should be treated as no headers"""
        result = await location_service.get_user_location(
            user_id="u01",
            headers={}
        )

        assert result.source == "mock_data"

# ============================================================
# TEST: Edge Cases
# ============================================================

class TestEdgeCases:
    """Edge case tests"""

    @pytest.mark.asyncio
    async def test_headers_with_whitespace(
        self, location_service
    ):
        """Headers with whitespace should be trimmed"""
        headers = {
            "X-User-Lat": "  21.0285  ",
            "X-User-Lng": "  105.8542  "
        }

        result = await location_service.get_user_location(
            user_id="u01",
            headers=headers
        )

        assert result.lat == 21.0285
        assert result.source == "headers"

    @pytest.mark.asyncio
    async def test_boundary_coordinates(
        self, location_service
    ):
        """Test boundary valid coordinates"""
        headers = {
            "X-User-Lat": "90",
            "X-User-Lng": "180"
        }

        result = await location_service.get_user_location(
            user_id="u01",
            headers=headers
        )

        assert result.lat == 90
        assert result.lng == 180
        assert result.source == "headers"

    @pytest.mark.asyncio
    async def test_none_values_in_headers_ignored(
        self, location_service
    ):
        """None values in headers should be ignored"""
        headers = {
            "X-User-Lat": None,
            "X-User-Lng": None
        }

        result = await location_service.get_user_location(
            user_id="u02",
            headers=headers
        )

        assert result.source == "mock_data"
```

### File: `tests/test_location_tool.py`

```python
# tests/test_location_tool.py
import pytest
from unittest.mock import AsyncMock, patch
from app.tools.location_tool import (
    GetUserLocationTool,
    GetUserLocationInput,
    GetUserLocationOutput
)
from app.services.location_service import LocationResult

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_location_service():
    """Mock LocationService for tool testing"""
    service = AsyncMock()
    service.get_user_location = AsyncMock()
    return service

@pytest.fixture
def location_tool(mock_location_service):
    tool = GetUserLocationTool()
    tool.location_service = mock_location_service
    return tool

# ============================================================
# TEST: Tool Interface
# ============================================================

class TestGetUserLocationTool:

    @pytest.mark.asyncio
    async def test_tool_returns_correct_format(self, location_tool, mock_location_service):
        """Tool should return dict with correct keys"""
        mock_location_service.get_user_location.return_value = LocationResult(
            lat=21.0285,
            lng=105.8542,
            source="headers",
            confidence=0.95
        )

        result = await location_tool._arun(user_id="u01")

        assert "lat" in result
        assert "lng" in result
        assert "source" in result
        assert "confidence" in result
        assert result["lat"] == 21.0285
        assert result["lng"] == 105.8542

    @pytest.mark.asyncio
    async def test_tool_passes_user_id_correctly(self, location_tool, mock_location_service):
        """Tool should pass user_id to service"""
        mock_location_service.get_user_location.return_value = LocationResult(
            lat=10.7769,
            lng=106.7009,
            source="mock_data"
        )

        await location_tool._arun(user_id="u02", address="TP.HCM")

        mock_location_service.get_user_location.assert_called_once_with(
            user_id="u02",
            address="TP.HCM",
            headers=None
        )

    @pytest.mark.asyncio
    async def test_tool_with_custom_headers(self, location_tool, mock_location_service):
        """Tool should accept custom headers"""
        mock_location_service.get_user_location.return_value = LocationResult(
            lat=16.0544,
            lng=108.2022,
            source="headers"
        )

        headers = {"X-User-Lat": "16.0544", "X-User-Lng": "108.2022"}
        result = await location_tool._arun(
            user_id="u03",
            address="Đà Nẵng",
            headers=headers
        )

        mock_location_service.get_user_location.assert_called_once()
        call_kwargs = mock_location_service.get_user_location.call_args.kwargs
        assert call_kwargs["headers"] == headers

# ============================================================
# TEST: Input Validation
# ============================================================

class TestInputValidation:

    def test_input_schema_requires_user_id(self):
        """user_id should be required"""
        schema = GetUserLocationInput.model_json_schema()

        # user_id should be required
        required_fields = schema.get("required", [])
        assert "user_id" in required_fields

    def test_input_schema_address_is_optional(self):
        """address should be optional"""
        schema = GetUserLocationInput.model_json_schema()

        required_fields = schema.get("required", [])
        assert "address" not in required_fields

    def test_valid_input(self):
        """Valid input should parse correctly"""
        input_data = GetUserLocationInput(
            user_id="u01",
            address="Hà Nội"
        )
        assert input_data.user_id == "u01"
        assert input_data.address == "Hà Nội"

    def test_input_without_address(self):
        """Input without address should work"""
        input_data = GetUserLocationInput(user_id="u01")
        assert input_data.user_id == "u01"
        assert input_data.address is None
```

---

## 6. Code Implementation

### Final File Structure

```
app/
├── services/
│   ├── __init__.py
│   ├── geocoding.py          # Geocoding API client
│   └── location_service.py    # Core location logic
└── tools/
    ├── __init__.py
    └── location_tool.py       # LangChain tool wrapper

app/db/
└── mock_data.py               # 10 sample users

tests/
├── __init__.py
├── conftest.py                # Pytest fixtures
├── test_location_service.py   # Service tests
└── test_location_tool.py      # Tool tests
```

### Run Tests

```bash
# Chạy tất cả tests
pytest tests/test_location_service.py tests/test_location_tool.py -v

# Chạy với coverage
pytest tests/ --cov=app.services.location_service --cov=app.tools.location_tool

# Chạy specific test class
pytest tests/test_location_service.py::TestGPSHeaders -v

# Chạy với asyncio
pytest tests/ -v --asyncio-mode=auto
```

---

## Checklist

- [ ] Tạo `app/services/location_service.py`
- [ ] Tạo `app/services/geocoding.py`
- [ ] Tạo `app/db/mock_data.py` với 10 users
- [ ] Tạo `app/tools/location_tool.py`
- [ ] Tạo `tests/test_location_service.py`
- [ ] Tạo `tests/test_location_tool.py`
- [ ] Chạy tests → all green ✓
- [ ] Update `app/tools/registry.py` để register tool
