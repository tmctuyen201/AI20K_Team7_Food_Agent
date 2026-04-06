import os
from dotenv import load_dotenv
from src.core.gemini_provider import GeminiProvider
from src.agent.agent import ReActAgent
from src.tools.food_tools import FOOD_TOOLS_CONFIG

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

llm = GeminiProvider(model_name="gemini-3.1-flash-lite-preview", api_key=api_key)
agent = ReActAgent(llm=llm, tools=FOOD_TOOLS_CONFIG, max_steps=5)

# 5 TEST CASES THIẾT KẾ ĐỂ "FLEX" VỚI GIÁM KHẢO
test_cases = [
    # 5. Multi-step Reasoning (Tư duy nhiều bước): Kết hợp cả GPS, Giờ, và Món ăn
    "Tôi đang ở đâu? Giờ này là giờ nào? Dựa vào 2 yếu tố đó, hãy gợi ý món ăn phù hợp nhất."
]

print("🚀 BẮT ĐẦU CHẠY 5 TEST CASES ĐÁNH GIÁ HỆ THỐNG")
for i, query in enumerate(test_cases, 1):
    print(f"\n{'='*60}")
    print(f"👉 TEST CASE {i}: {query}")
    print(f"{'='*60}")
    agent.run(query)