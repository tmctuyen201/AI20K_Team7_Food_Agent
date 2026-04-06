import math
import requests
import json
from typing import Type, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class SearchPlacesInput(BaseModel):
    lat: float = Field(description="Vĩ độ hiện tại (Latitude)")
    lng: float = Field(description="Kinh độ hiện tại (Longitude)")
    keyword: str = Field(description="Món ăn hoặc tên quán (vd: phở, bún chả)")
    preference: str = Field(default="prominence", description="Ưu tiên: 'distance' hoặc 'prominence'")

class SearchPlacesTool(BaseTool):
    name: str = "Search Places API"
    description: str = "Tìm kiếm quán ăn qua Google Maps. Trả về JSON gồm: name, rating, address, distance, price (nếu có)."
    args_schema: Type[BaseModel] = SearchPlacesInput
    return_direct: bool = True 

    SERP_API_KEY: str = ""

    def _haversine(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        r = 6371.0
        p = math.pi / 180
        a = 0.5 - math.cos((lat2 - lat1) * p)/2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lng2 - lng1) * p)) / 2
        return 2 * r * math.asin(math.sqrt(a))

    def _run(self, lat: float, lng: float, keyword: str, preference: str = "prominence") -> str:
        query = f"{keyword} {'gần đây' if preference == 'distance' else 'ngon'}"
        
        params = {
            "engine": "google_maps",
            "type": "search",
            "q": query,
            "ll": f"@{lat},{lng},16z",
            "hl": "vi",
            "gl": "vn",
            "api_key": self.SERP_API_KEY
        }

        try:
            # 1. Bắt lỗi kết nối mạng/timeout
            response = requests.get("https://serpapi.com/search", params=params, timeout=15)
            response.raise_for_status() # Nếu lỗi 401, 403, 500 nó sẽ nhảy xuống except ngay
            
            data = response.json()
            
            if "error" in data:
                return json.dumps({"status": "ERROR", "message": data["error"]}, ensure_ascii=False)

            results = []
            # 2. Kiểm tra xem có local_results không để tránh lỗi loop trên None
            local_results = data.get("local_results", [])
            
            for p in local_results:
                gps = p.get("gps_coordinates")
                p_lat = gps.get("latitude") if gps else None
                p_lng = gps.get("longitude") if gps else None
                
                # Tính khoảng cách an toàn
                if p_lat is not None and p_lng is not None:
                    dist_km = self._haversine(lat, lng, p_lat, p_lng)
                else:
                    dist_km = 999.0

                # 3. Khởi tạo trực tiếp, tối ưu hơn copy()
                res_item = {
                    "name": p.get("title", "N/A"),
                    "rating": p.get("rating", 0),
                    "address": p.get("address", "N/A"),
                    "distance": f"{int(dist_km*1000)}m" if dist_km < 1 else f"{dist_km:.1f}km",
                    "_dist_raw": dist_km
                }
                
                # Thêm price nếu có
                price = p.get("price")
                if price:
                    res_item["price"] = price
                
                results.append(res_item)

            # 4. Sắp xếp thông minh
            if preference == "distance":
                results.sort(key=lambda x: x["_dist_raw"])
            else:
                # Rating cao lên đầu, nếu bằng rating thì ưu tiên thằng gần hơn chút
                results.sort(key=lambda x: (-x["rating"], x["_dist_raw"]))

            # 5. Cắt lấy top 5 và dọn dẹp
            final_list = []
            for r in results[:5]:
                r.pop("_dist_raw", None)
                final_list.append(r)

            return json.dumps({
                "status": "OK" if final_list else "ZERO_RESULTS",
                "results": final_list
            }, ensure_ascii=False, indent=4)

        except requests.exceptions.RequestException as e:
            return json.dumps({"status": "ERROR", "message": f"Lỗi kết nối API: {str(e)}"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "ERROR", "message": f"Lỗi hệ thống: {str(e)}"}, ensure_ascii=False)
