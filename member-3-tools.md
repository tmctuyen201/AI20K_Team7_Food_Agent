import math
import requests

SERP_API_KEY = "c2f31a0fdeb43857c8163649f9478603b13db8034a8ff98a5275d99eb2034820"


def haversine_km(lat1, lng1, lat2, lng2):
    """Tính khoảng cách chim bay giữa 2 tọa độ theo km."""
    r = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def format_distance(km):
    """Format khoảng cách để không bao giờ bị None."""
    if km is None:
        return "N/A"
    if km < 1:
        return f"{int(round(km * 1000))} m"
    return f"{km:.2f} km"


def build_query(keyword, preference):
    """Tạo query tự nhiên hơn cho Google Maps."""
    keyword = keyword.strip()

    if preference == "distance":
        return f"{keyword} gần đây"
    if preference == "prominence":
        return f"{keyword} ngon"
    return keyword


def extract_price(place):
    """
    Lấy thông tin giá nếu có.
    SerpApi/Google Maps có thể trả về dưới nhiều field khác nhau.
    """
    possible_keys = [
        "price",
        "price_level",
        "pricing",
    ]

    for key in possible_keys:
        value = place.get(key)
        if value:
            return value

    return None


def search_restaurants(lat, lng, keyword, preference="prominence"):
    """
    lat, lng: tọa độ user
    keyword: món ăn, ví dụ 'phở', 'bún chả'
    preference: 'distance' hoặc 'prominence'
    """
    query = build_query(keyword, preference)

    params = {
        "engine": "google_maps",
        "type": "search",
        "q": query,
        "ll": f"@{lat},{lng},17z",
        "hl": "vi",
        "gl": "vn",
        "no_cache": "true",
        "api_key": SERP_API_KEY,
    }

    response = requests.get("https://serpapi.com/search", params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise Exception(data["error"])

    results = data.get("local_results", [])
    restaurants = []

    for place in results:
        gps = place.get("gps_coordinates") or {}
        place_lat = gps.get("latitude")
        place_lng = gps.get("longitude")

        computed_distance = None
        if place_lat is not None and place_lng is not None:
            computed_distance = haversine_km(lat, lng, place_lat, place_lng)

        distance_text = place.get("distance")
        if not distance_text:
            distance_text = format_distance(computed_distance)

        restaurant = {
            "name": place.get("title", "Không rõ tên"),
            "rating": place.get("rating", 0),
            "reviews": place.get("reviews", 0),
            "address": place.get("address", "Không rõ địa chỉ"),
            "distance": distance_text,
            "distance_km": computed_distance if computed_distance is not None else float("inf"),
        }

        price = extract_price(place)
        if price:
            restaurant["price"] = price

        restaurants.append(restaurant)

    if preference == "distance":
        restaurants.sort(key=lambda x: x["distance_km"])
    else:
        restaurants.sort(
            key=lambda x: (
                x["rating"] if x["rating"] is not None else 0,
                x["reviews"] if x["reviews"] is not None else 0,
                -(x["distance_km"] if x["distance_km"] != float("inf") else 999999),
            ),
            reverse=True,
        )

    return restaurants, data


def main():
    lat = 20.991262659315687
    lng = 105.94620560858695
    keyword = "phở"
    preference = "distance"   # "distance" hoặc "prominence"

    results, raw = search_restaurants(lat, lng, keyword, preference)

    print("=== DEBUG ===")
    print("Search params location:", f"@{lat},{lng},17z")
    print("Results found:", len(results))
    print("")

    print("=== KẾT QUẢ ===")
    for i, r in enumerate(results[:5], 1):
        print(f"{i}. {r['name']}")
        print(f"   ⭐ Rating: {r['rating']}")
        print(f"   📍 Address: {r['address']}")
        print(f"   🚶 Distance: {r['distance']}")
        if "price" in r:
            print(f"   💰 Price: {r['price']}")
        print("")


if __name__ == "__main__":
    main()