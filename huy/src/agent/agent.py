import os
import re
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

class ReActAgent:
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return f"""
        Bạn là một ReAct Agent thực hiện từng bước. TUYỆT ĐỐI KHÔNG sử dụng kiến thức có sẵn để đoán vị trí hoặc tên nhà hàng.
        
        CÁC CÔNG CỤ (TOOLS):
        {tool_descriptions}

        QUY TẮC SỐNG CÒN (CRITICAL):
        1. Bạn chỉ được phép viết đến dòng 'Action Input:'. SAU ĐÓ PHẢI DỪNG LẠI.
        2. TUYỆT ĐỐI KHÔNG TỰ VIẾT TỪ 'Observation:'. Hệ thống sẽ tự chạy công cụ và cung cấp Observation cho bạn.
        3. Nếu chưa gọi tool 'search_food' và chưa có Observation từ nó, KHÔNG ĐƯỢC CHỐT 'Final Answer:'.
        4. GUARDRAIL AN TOÀN: Nếu người dùng hỏi về Toán học, Lịch sử, Lập trình, hoặc bất cứ thứ gì KHÔNG LIÊN QUAN đến tìm quán ăn/địa điểm, TUYỆT ĐỐI KHÔNG giải thích hay trả lời. Hãy chốt ngay lập tức: "Final Answer: Xin lỗi, tôi chỉ là trợ lý hỗ trợ tìm kiếm địa điểm ăn uống."
        
        ĐỊNH DẠNG MỘT BƯỚC SUY NGHĨ:
        Thought: Mình cần làm gì tiếp theo?
        Action: [Tên công cụ]
        Action Input: [Tham số]
        """

    def run(self, user_input: str) -> str:
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})
        
        current_prompt = f"User Query: {user_input}\n"
        steps = 0

        while steps < self.max_steps:
            result = self.llm.generate(current_prompt, system_prompt=self.get_system_prompt())
            response_text = result["content"]
            
            print(f"\n[STEP {steps + 1}] -------------------------")
            print(response_text)
            
            # Bóc tách chuỗi
            action_match = re.search(r"Action:\s*(.*)", response_text)
            input_match = re.search(r"Action Input:\s*(.*)", response_text)
            
            # Xử lý Logic an toàn, tránh lỗi NoneType
            if action_match:
                tool_name = action_match.group(1).strip()
                args = input_match.group(1).strip() if input_match else ""
                
                # Thực thi tool
                observation = self._execute_tool(tool_name, args)
                print(f"Observation (Real): {observation}")
                logger.log_event("TOOL_EXECUTION", {"tool": tool_name, "args": args, "result": observation})
                
                # Cắt bỏ toàn bộ phần AI tự bịa (nếu nó lỡ sinh ra chữ Observation hoặc Final Answer)
                clean_response = response_text.split("Observation:")[0].strip()
                
                # Nối kết quả thật vào để chạy bước tiếp theo
                current_prompt += f"\n{clean_response}\nObservation: {observation}\n"
                
            elif "Final Answer:" in response_text:
                final_answer = response_text.split("Final Answer:")[-1].strip()
                logger.log_event("AGENT_END", {"steps": steps + 1, "status": "success", "final_answer": final_answer})
                return final_answer
                
            else:
                logger.log_event("AGENT_ERROR", {"reason": "Parser Error - No Action or Final Answer"})
                print("\n❌ Lỗi Parser: AI không đưa ra Action cũng không chốt Final Answer.")
                break
                
            steps += 1
            
        logger.log_event("AGENT_END", {"steps": steps, "status": "timeout_or_error"})
        return "Xin lỗi, tôi đã suy nghĩ quá 5 bước mà chưa tìm ra kết quả."

    def _execute_tool(self, tool_name: str, args: str) -> str:
        for tool in self.tools:
            if tool['name'] == tool_name:
                try:
                    return str(tool['func'](args))
                except Exception as e:
                    return f"Error executing tool: {str(e)}"
        return f"Tool {tool_name} not found."
    