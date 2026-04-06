import json
from datetime import datetime

def get_location(args=None):
    """Giả lập lấy GPS hiện tại."""
    # Bố có thể đổi địa chỉ ở đây để test
    return "1 P. Nguyễn Cảnh Dị, Khu đô thị Bắc Linh Đàm, Định Công, Hà Nội"

from datetime import datetime

def get_current_time(args=None):
    """Lấy thời gian hiện tại và diễn giải rõ buổi trong ngày."""
    now = datetime.now()
    
    hour = now.hour
    minute = now.minute
    
    # Xác định buổi
    if 5 <= hour < 12:
        period_vi = "buổi sáng"
    elif 12 <= hour < 17:
        period_vi = "buổi trưa/chiều"
    elif 17 <= hour < 22:
        period_vi = "buổi tối"
    else:
        period_vi = "ban đêm"
    
    # Format 12h + AM/PM
    time_12h = now.strftime("%I:%M %p")  # ví dụ: 12:21 PM
    
    return f"Bây giờ là {time_12h} ({period_vi})"

def search_food(query):
    """Tìm quán ăn dựa trên từ khóa và địa phương."""
    query = query.lower()
    
    # Kịch bản 1: Tìm dê ở Hà Nội
    if "dê" in query and "hà nội" in query:
        return json.dumps([
            {"name": "Dê Núi 9 Phút - Linh Đàm", "address": "KĐT Bắc Linh Đàm, Định Công", "status": "Đang mở cửa"}
        ], ensure_ascii=False)
        
    # Kịch bản 2: Tìm dê ở Ninh Bình
    elif "dê" in query and "ninh bình" in query:
        return json.dumps([
            {"name": "Nhà Hàng Vũ Bảo TP Ninh Bình", "address": "Phố Tân Thịnh, Hoa Lư", "status": "Đang mở cửa"}
        ], ensure_ascii=False)
        
    # Kịch bản 3: Tìm cơm niêu ở Ninh Bình
    elif "cơm niêu" in query and "ninh bình" in query:
        return json.dumps([
            {"name": "Cơm Niêu Việt Xưa - Tam Cốc", "status": "Đang mở cửa"}
        ], ensure_ascii=False)
        
    # Kịch bản 4: Không tìm thấy
    return "Không có dữ liệu nhà hàng cho khu vực hoặc món ăn này. Hãy thử khu vực khác."

# Cập nhật danh sách công cụ
FOOD_TOOLS_CONFIG = [
    {
        "name": "get_location",
        "description": "Lấy vị trí GPS hiện tại. Input: 'None'.",
        "func": get_location
    },
    {
        "name": "get_current_time",
        "description": "Xem giờ hiện tại để biết có phải ban đêm không (Midnight Craving). Input: 'None'.",
        "func": get_current_time
    },
    {
        "name": "search_food",
        "description": "Tìm quán ăn. Input: Tên món + Địa điểm (VD: cơm niêu Ninh Bình).",
        "func": search_food
    }
]