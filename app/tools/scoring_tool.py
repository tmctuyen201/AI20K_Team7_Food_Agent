import json
from typing import List, Dict, Any, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class ScoringInput(BaseModel):
    places: List[Dict[str, Any]] = Field(description="Danh sách các quán ăn từ kết quả tìm kiếm")
    w_quality: float = Field(default=0.6, description="Trọng số chất lượng (0.1 - 0.9)")
    w_distance: float = Field(default=0.4, description="Trọng số khoảng cách (0.1 - 0.9)")

class ScoringTool(BaseTool):
    name: str = "calculate_scores"
    description: str = (
        "Dùng để tính điểm và xếp hạng quán ăn dựa trên Rating và Khoảng cách. "
        "Công thức: Score = (Rating * w_quality) + (w_distance / Distance_km). "
        "Hãy tăng w_distance nếu khách hàng đang đói hoặc vội."
    )
    args_schema: Type[BaseModel] = ScoringInput
    return_direct: bool = True 

    def _parse_km(self, val: Any) -> float:
        """Parse an toàn khoảng cách về float km."""
        try:
            s = str(val).lower().strip()
            if 'km' in s: return float(s.replace('km', '').strip())
            if 'm' in s: return float(s.replace('m', '').strip()) / 1000
            return float(s)
        except: 
            return 1.0 # Giá trị an toàn tránh lỗi logic

    def _run(self, places: List[Dict[str, Any]], w_quality: float = 0.6, w_distance: float = 0.4) -> str:
        if not places: 
            return "Không có dữ liệu để xếp hạng."

        scored = []
        for p in places:
            # Lấy rating và distance an toàn (mặc định 0 và 1.0 nếu thiếu)
            rating = float(p.get("rating") or 0)
            dist = self._parse_km(p.get("distance") or 1.0)
            
            # Tính toán: chặn dist tối thiểu 0.1km để tránh chia cho 0 và điểm ảo
            total_score = (rating * w_quality) + (w_distance / max(dist, 0.1))
            
            # Giữ nguyên thông tin cũ và thêm điểm số mới
            scored.append({**p, "total_score": round(total_score, 2)})

        # Sắp xếp giảm dần theo điểm và lấy Top 5
        top_5 = sorted(scored, key=lambda x: x["total_score"], reverse=True)[:5]

        # Trả về kết quả dưới dạng chuỗi văn bản sạch để Agent in ra cho User
        output = [f"=== BẢNG XẾP HẠNG (Chất lượng: {w_quality} / Gần: {w_distance}) ==="]
        for i, r in enumerate(top_5, 1):
            output.append(f"{i}. {r['name']} - Điểm tổng hợp: {r['total_score']}")
        
        return "\n".join(output)
