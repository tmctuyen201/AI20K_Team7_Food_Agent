"""Mock user location data (Phase 1 – no real GPS)."""

from __future__ import annotations

from app.db.models import LatLng

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

DEFAULT_LOCATION = {"lat": 21.0285, "lng": 105.8542}


def get_mock_location(user_id: str) -> LatLng:
    """Return LatLng for a known user_id, or the default Hanoi location."""
    user = next((u for u in MOCK_USERS if u["user_id"] == user_id), None)
    if user is None:
        # Fallback to default
        return LatLng(lat=DEFAULT_LOCATION["lat"], lng=DEFAULT_LOCATION["lng"])
    return LatLng(lat=user["lat"], lng=user["lng"])