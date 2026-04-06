# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: Nhóm 7 - Foodie Agent
- **Team Members**: Nguyễn Duy Anh, Nguyễn Thị Cẩm Nhung, Trịnh Đắc Phú, Trịnh Minh Công Tuyền, Trần Hữu Gia Huy 
- **Deployment Date**: 2026-04-06

---

## 1. Executive Summary

Báo cáo đánh giá hiệu năng của **Foodie Agent** - trợ lý AI hỗ trợ tìm kiếm và xếp hạng quán ăn dựa trên vị trí thực tế. Qua thử nghiệm, Agent cho thấy khả năng gọi Tool chính xác nhưng cần tối ưu hóa vòng lặp suy luận để hoàn thành các tác vụ đa bước (Multi-step).

- **Success Rate**: **75%** (Giải quyết chính xác 3/4 kịch bản thử nghiệm).
- **Key Outcome**: Kỹ thuật **Few-shot Prompting** giúp giảm tỷ lệ lỗi định dạng từ **75% xuống còn 15%**, cải thiện đáng kể độ ổn định hệ thống.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation
Hệ thống vận hành theo cơ chế **Thought - Action - Observation**. 
- **Quy trình:** Phân tích nhu cầu -> Xác định vị trí -> Tìm kiếm địa điểm -> Xếp hạng (Scoring).
- **Vấn đề:** `Avg. Steps = 1`, Agent có xu hướng kết thúc sớm sau một Action đơn lẻ. Cần cấu hình lại luồng để duy trì chuỗi hành động dài hơn.


### 2.2 Tool Definitions (Inventory)

| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `get_user_location` | `JSON` | Xác định tọa độ (Lat/Lng) từ `mock_users.json` hoặc địa chỉ nhập vào. |
| `search_places_api` | `JSON` | Truy vấn dữ liệu từ Google Maps (SerpApi), tích hợp tính khoảng cách **Haversine**. |
| `calculate_scores` | `JSON` | Thuật toán xếp hạng Top 5 dựa trên trọng số $w_{quality}$ và $w_{distance}$. |

### 2.3 LLM Providers Used
- **Primary**: ChatGPT 4o mini (Tối ưu về tốc độ phản hồi và chi phí vận hành).

---

## 3. Telemetry & Performance Dashboard

Dữ liệu ghi nhận từ quá trình vận hành thực tế:

- **Average Latency (P50)**: **1.74s**
- **Max Latency (P99)**: **2.43s** (Ghi nhận tại các truy vấn khởi tạo như "xin chào").
- **Average Tokens per Task**: **~50 tokens** (Input 15 / Output 35).
- **Tool Accuracy**: **100%** (Tất cả lệnh gọi Tool đều khớp chính xác tham số `lat`, `lng` và định dạng JSON).

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Case Study: Lỗi ngắt quãng quy trình (Workflow Interruption)
- **Input**: *"Tôi muốn tìm thông tin quán ăn tại Gia Lâm, Hà Nội"*
- **Observation**: Agent gọi thành công `get_user_location` nhưng lập tức trả về phản hồi (`STOP`) thay vì tiếp tục bước tìm kiếm quán ăn.
- **Root Cause**: 
    - Cấu hình hệ thống bị giới hạn ở `max_iterations = 1`.
    - Prompt chưa mô tả chặt chẽ tính liên kết giữa các Tool (Dependency).
- **Fix**: 
    - Nâng cấp cấu hình lên `max_iterations = 5`.
    - Bổ sung hướng dẫn Workflow vào System Prompt: *Phải thực hiện đủ chuỗi hành động: Định vị -> Tìm kiếm -> Xếp hạng.*

---

## 5. Ablation Studies & Experiments

### Experiment: Prompt v1 (Basic) vs Prompt v2 (Few-shot)
- **Thay đổi**: Thêm các ví dụ mẫu (User Query -> Thought -> Action) vào Prompt.
- **Kết quả**: Giảm lỗi format khoảng **60%**. Agent hiểu rõ cách truyền tham số cho các hàm toán học.

| Case | Chatbot Baseline | Agent Result | Winner |
| :--- | :--- | :--- | :--- |
| Tìm quán mới mở | Dữ liệu tĩnh cũ | Gọi API thời gian thực | **Agent** |
| Tính khoảng cách | Ước lượng cảm tính | Tính toán Haversine chuẩn | **Agent** |
| Câu hỏi đa bước | Hoàn thành tốt | Bị dừng giữa chừng | **Chatbot** |

---

## 6. Production Readiness Review

- **Security**: Thực hiện kiểm soát đầu vào (Sanitization) cho các từ khóa để tránh Prompt Injection.
- **Guardrails**: Sử dụng cơ chế **Safe-Distance Clipping** ($\max(dist, 0.1)$) trong logic xử lý của Nhung để ngăn chặn lỗi chia cho 0 và ổn định điểm số khi quán ở quá gần.
- **Scaling**: Đề xuất chuyển dịch sang framework **LangGraph** để quản lý trạng thái (State) chặt chẽ, đảm bảo Agent hoàn thành 100% workflow trước khi kết thúc.

---