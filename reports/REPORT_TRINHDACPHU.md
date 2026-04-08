# Báo cáo cá nhân: Lab 3 - Chatbot vs ReAct Agent

- **Họ và tên**: TRỊNH ĐẮC PHÚ
- **Mã sinh viên**: 2A202600322
- **Ngày**: 2026-04-06

---

## I. Đóng góp kỹ thuật (15 điểm)

Trong quá trình làm Lab 3, tôi tập trung vào việc xây dựng module **guardrail** để tăng độ an toàn/ổn định cho ReAct Agent, đồng thời cải thiện log để phục vụ debugging và viết báo cáo.

- **Modules/Files đã triển khai**:
  - `app/core/guardrail.py`: xây dựng module **guardrail** (các kiểm tra sau mỗi vòng lặp/hoặc theo input) nhằm chặn các trường hợp bất thường và trả về thông điệp hướng dẫn người dùng.
  - `app/core/logging.py`: bổ sung formatter để **loại bỏ mã màu ANSI** khi ghi log theo session, giúp file `.log` sạch và dễ parse.
  - `scripts/generate_log_report.py`: viết script **tự động tạo báo cáo Markdown** từ file log session.
  - `reports/session_sess_1e717e63.md`: báo cáo sinh tự động từ log mẫu.
- **Điểm nhấn code**:
  - `app/core/guardrail.py`:
    - Thiết kế `GuardrailResult(triggered, name, message)` để trả kết quả guardrail theo chuẩn thống nhất.
    - Các guardrail chính:
      - `check_irrelevant_input`: phát hiện câu hỏi **không liên quan** đến ăn uống/địa điểm (ví dụ “thời tiết”) và trả lời gợi ý truy vấn đúng ngữ cảnh; đồng thời **bỏ qua** các câu chào hỏi.
      - `_check_zero_results`: khi không có kết quả trả về từ API mà vẫn có `keyword`, trả lời gợi ý đổi từ khóa/tăng bán kính.
      - `_check_max_retries`: khi người dùng từ chối nhiều lần, yêu cầu bổ sung ràng buộc (ngân sách/khu vực/phong cách).
      - `_check_midnight_filter`: cảnh báo khung giờ đêm (22:00–05:00) nếu ít quán mở cửa.
    - Log các sự kiện như `guardrail_irrelevant_input`, `guardrail_zero_results`,... để tiện truy vết.
  - `SessionLogHandler` gắn `FileHandler` vào root logger và set formatter dạng `%(message)s`, nhưng được bọc thêm bước strip ANSI.
  - Script report parse các dòng theo cấu trúc: `timestamp level event logger key=value...`, gom thành:
    - Tổng quan session (session_id, user_id, thời gian, số lượt chat)
    - Thống kê tool usage
    - Tóm tắt theo từng lượt người dùng (turn)
    - Warnings/Errors theo event
- **Tương tác với ReAct loop**:
  - Log giúp quan sát rõ các pha: `agent_run_start` → `llm_call_*` → (nếu có) `tool_call_*` → `agent_run_done*`.
  - Báo cáo tự động giúp nhanh chóng phát hiện “turn có tool nhưng không có final response”, từ đó khoanh vùng lỗi ở vòng lặp tác nhân (agent loop).

---

## II. Nghiên cứu tình huống Debug (10 điểm)

- **Mô tả vấn đề**:
  - Trong session `sess_1e717e63`, người dùng hỏi *“thời tiết hôm nay thế nào?”* (2026-04-06 10:49:58 UTC) — đây là câu hỏi **ngoài phạm vi** của Foodie Agent (tìm quán ăn). Agent đã trả lời xin lỗi và hướng người dùng quay lại tìm nhà hàng, nhưng turn này vẫn bị ghi nhận `session_no_tools` (warning), gây nhiễu khi đọc log và không có cơ chế chuẩn hoá “ngoài phạm vi”.
- **Nguồn log**:
  - File: `logs/session_sess_1e717e63.log`
  - Dấu hiệu chính:
    - `user_message ... message='thời tiết hôm nay thế nào?'`
    - `agent_run_done_no_tool ... final_response_preview='Xin lỗi, nhưng tôi không có khả năng cung cấp thông tin thời tiết...'`
    - `session_no_tools` xuất hiện ngay sau đó
- **Chẩn đoán**:
  - Với các truy vấn ngoài phạm vi, nếu không có guardrail, hệ thống dễ rơi vào 2 vấn đề:
    1) Trả lời không nhất quán (tuỳ model/prompt), không “đóng vòng” theo một format chuẩn.
    2) Logging/monitoring bị nhiễu bởi `session_no_tools` dù đây là hành vi bình thường (không cần tool).
  - Guardrail `check_irrelevant_input` trong `app/core/guardrail.py` được thiết kế để chuẩn hoá phản hồi cho các câu hỏi ngoài phạm vi, và có whitelist cho các câu chào hỏi như “xin chào/hello”.
- **Giải pháp/đề xuất fix**:
  - Tích hợp guardrail “ngoài phạm vi” theo hướng **fail-fast**:
    - Nếu `check_irrelevant_input(...)` kích hoạt: set `state["final_response"]` theo `GuardrailResult.message` và kết thúc turn ngay, tránh gọi LLM/tool không cần thiết.
    - Ghi log `guardrail_irrelevant_input` để dễ thống kê tỷ lệ truy vấn ngoài phạm vi.
  - Giảm nhiễu log:
    - Cân nhắc hạ `session_no_tools` từ `warning` xuống `info` cho các turn không cần tool (chào hỏi/ngoài phạm vi).

---

## III. Nhận xét cá nhân: Chatbot vs ReAct (10 điểm)

1. **Lý luận (Reasoning)**:
   - ReAct hữu ích khi cần hành động theo từng bước (lấy vị trí → tìm Places → chấm điểm → trả top 5).
   - Với câu hỏi có thể trả lời trực tiếp (chào hỏi), Chatbot phản hồi nhanh, ReAct thường không cần tool.
2. **Độ tin cậy (Reliability)**:
   - ReAct có thể “tệ hơn” Chatbot nếu pipeline tool-call không hoàn chỉnh: đã gọi tool nhưng không trả câu trả lời cuối, gây trải nghiệm “đứng/không phản hồi”.
3. **Quan sát (Observation)**:
   - Observation từ tool (ví dụ lat/lng của Gia Lâm) là tín hiệu quan trọng để bước tiếp theo (search places). Nếu observation không được đưa lại vào LLM/không có vòng lặp tiếp theo, ReAct mất lợi thế.

---

## IV. Cải tiến tương lai (5 điểm)

- **Khả năng mở rộng (Scalability)**:
  - Tách tool execution sang hàng đợi async (Celery/RQ) hoặc job queue, cho phép retry và theo dõi trạng thái.
- **An toàn (Safety)**:
  - Thêm lớp “supervisor”/rule-based guard: kiểm tra tool args, giới hạn bán kính, chống prompt injection trong dữ liệu Places.
- **Hiệu năng (Performance)**:
  - Cache kết quả geocoding/places theo (query, lat/lng, radius).
  - Dùng log dạng JSON (production) + pipeline phân tích (ELK/OpenTelemetry) để truy vết theo session/tool_call_id.

---

> [!NOTE]
> Bạn hãy đổi tên file này thành `REPORT_[TEN_BAN].md` theo yêu cầu nộp bài. Nếu hệ thống yêu cầu nộp trong thư mục khác, bạn có thể copy nội dung từ `reports/REPORT_TEMPLATE_VI.md`.
