# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyễn Thị Cẩm Nhung
- **Student ID**: 2A202600208
- **Date**: 2026-04-06

---

## I. Technical Contribution 
Trong dự án này, tôi chịu trách nhiệm chính trong việc thiết kế và triển khai hệ thống công cụ (**Tools**) cung cấp dữ liệu thực tế và khả năng tư duy xếp hạng cho Agent.

- **Modules Implemented**: 
    - `app/tools/google_search_tool.py`: Công cụ truy vấn địa điểm thực tế từ Google Maps API thông qua SerpApi.
    - `app/tools/scoring_tool.py`: Thuật toán đánh giá và xếp hạng địa điểm thông minh.

- **Code Highlights**: 

    **1. Haversine Formula**: Triển khai thuật toán tính khoảng cách mặt cầu để loại bỏ sai số GPS, đảm bảo tính toán chính xác trên bề mặt Trái Đất thay vì dùng khoảng cách phẳng thông thường:

    $$a = \sin^2\left(\frac{\Delta lat}{2}\right) + \cos(lat_1) \cdot \cos(lat_2) \cdot \sin^2\left(\frac{\Delta lng}{2}\right)$$

    $$Distance = 2 \cdot R \cdot \arcsin(\sqrt{a})$$

    **2. Weighted Scoring Logic**: Thiết lập công thức tính điểm tổng hợp giúp Agent tự động hóa việc ra quyết định dựa trên mức độ ưu tiên của người dùng (Đói/Vội vs Muốn ăn ngon):

    $$Score = (Rating \times w_{quality}) + \left(\frac{w_{distance}}{\max(dist_{km}, 0.1)}\right)$$

- **Documentation**: Toàn bộ dữ liệu trả về từ Tool được chuẩn hóa dưới dạng văn bản sạch (**Plain Text**). Điều này giúp Agent dễ dàng "đọc" thông tin trong vòng lặp ReAct để thực hiện bước `Thought` tiếp theo một cách chính xác mà không tốn quá nhiều Token.

---

## II. Debugging Case Study 

- **Problem Description**: Trong quá trình kiểm thử, Agent gặp lỗi logic định vị nghiêm trọng. Khi người dùng ở Việt Nam yêu cầu tìm quán ăn, Agent lại tính toán và đề xuất các địa điểm có khoảng cách sai lệch hàng nghìn km (kết quả trả về tại **Mỹ**), khiến hệ thống xếp hạng bị vô hiệu hóa.
- **Log Source (Terminal Evidence)**: 
  ```text
  PS D:\Github\AI20K_Team7_Food_Agent\app\tools> python .\google_search_tool.py
  === KẾT QUẢ ===
  1. Pho 1
     ⭐ Rating: 4.3
     📍 Address: 2800 N Military Trl STE 117, West Palm Beach, FL 33409
     🚶 Distance: None
    ```
  > *Observation: [{"name": "Pho 1", "distance": "8540km", "rating": 4.3}]*
- **Diagnosis**: Nguyên nhân do ban đầu sử dụng phép tính khoảng cách **Euclide** (đường thẳng trên mặt phẳng) trực tiếp trên tọa độ kinh độ/vĩ độ thô. Vì Trái Đất hình cầu, việc coi kinh/vĩ độ là tọa độ phẳng gây ra sai số khổng lồ, đặc biệt là khi tính toán giữa các bán cầu khác nhau.
- **Solution**: Tôi đã triển khai hàm `_haversine` dựa trên bán kính Trái Đất ($R \approx 6371km$) để quy đổi tọa độ góc thành khoảng cách mét thực tế.  
  **Kết quả:** Khoảng cách đã được hiển thị chuẩn xác (ví dụ từ 8540km về còn 1.2km), giúp `ScoringTool` hoạt động đúng logic và đưa quán gần nhất lên đầu.

---

## III. Personal Insights: Chatbot vs ReAct 

1. **Reasoning**: Khối `Thought` giúp Agent có khả năng lập kế hoạch. Thay vì trả lời dựa trên kiến thức tĩnh, Agent tự hiểu trình tự: **"Lấy vị trí -> Tìm kiếm thực tế -> Tính điểm xếp hạng"**. Đây là tư duy logic vượt trội mà Chatbot thông thường không thể thực hiện được.
2. **Reliability**: Agent thực hiện **tệ hơn** Chatbot trong các câu hỏi xã giao đơn giản (Small talk). Việc ép một câu chào hỏi qua vòng lặp ReAct gây ra độ trễ (Latency) không cần thiết và lãng phí tài nguyên API.
3. **Observation**: Phản hồi từ môi trường (Observations) là "kim chỉ nam". Nếu kết quả trả về không đủ, Agent sẽ tự động `Thought` để mở rộng bán kính tìm kiếm hoặc thay đổi từ khóa mà không cần người dùng yêu cầu lại.

---

## IV. Future Improvements (5 Points)

- **Scalability**: Sử dụng kiến trúc **Asynchronous (Asyncio)** để gọi nhiều API Tool cùng lúc, giảm thiểu thời gian chờ (Blocking) của hệ thống.
- **Safety**: Triển khai một **Supervisor LLM** để kiểm duyệt các `Action` trước khi thực thi, đảm bảo Agent không gọi Tool sai mục đích.
- **Performance**: Tích hợp **Semantic Caching** để lưu trữ kết quả của các truy vấn phổ biến, giúp phản hồi ngay lập tức cho các yêu cầu trùng lặp mà không cần tính toán lại.

---
