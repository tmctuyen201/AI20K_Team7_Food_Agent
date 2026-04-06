# Backend-2: Agent Core

## Architecture Overview

Foodie Agent là ReAct-based chatbot tìm quán ăn qua Google Places API.

**Tech stack:** Python · FastAPI · LangGraph · MongoDB · Google Maps Platform

### Project Structure

```
app/
├── main.py               # FastAPI app, router mount
├── api/
│   ├── chat.py           # WebSocket endpoint
│   ├── session.py        # Auth endpoints
│   └── history.py        # History endpoints
├── agent/                # ⭐ ReAct Agent
├── tools/                # ⭐ Tool definitions
├── db/                   # MongoDB models & queries
├── services/             # Google API clients
└── core/
    ├── config.py         # Env vars
    ├── auth.py           # JWT logic
    └── guardrail.py     # ⭐ Guardrail layer
```

---

## Feature: Agent Core

### Nhiệm vụ

1. Xây dựng **ReAct loop** với LangGraph
2. Quản lý **state** giữa các vòng lặp
3. Gọi **tools** để thu thập thông tin
4. Trả về **Top 5 quán** được xếp hạng

### LLM: Claude Sonnet 3.7 hoặc GPT-4o qua LiteLLM

---

### 2.1 ReAct Loop

```
User input
    │
    ▼
[Thought]     LLM phân tích intent, quyết định tool cần gọi
    │
    ▼
[Action]      Gọi tool (LocationTool / GoogleSearchTool / MemoryTool / ScoringTool)
    │
    ▼
[Observation] Nhận kết kết quả từ tool
    │
    ├── Chưa đủ thông tin → quay lại [Thought]
    │
    └── Đủ → Trả Top 5 quán về user
```

### 2.2 LangGraph State

```python
class AgentState(TypedDict):
    user_id: str
    user_message: str
    location: Optional[LatLng]
    keyword: Optional[str]
    places: list[Place]
    scored_places: list[ScoredPlace]
    shown_place_ids: list[str]
    rejection_count: int
    session_id: str
    next_page_token: Optional[str]
    response_tokens: list[str]
```

### 2.3 System Prompt

```
You are a Foodie Agent. Your goal is to find the top 5 restaurants.

Tools available:
- get_user_location(user_id): Get lat/lng from GPS or mock data
- search_google_places(location, keyword, sort_by, radius): Query Places API
- calculate_scores(places, weight_quality, weight_distance): Score & rank
- save_user_selection(user_id, place_id): Save to history

Rules:
1. If location is missing, ASK the user for their address.
2. Always check open_now before recommending.
3. Present 5 options with: Name, Rating, Distance, Why you might like it.
4. If user dislikes all 5, trigger expand_search (increase radius or change keyword).
5. After 3 consecutive rejections, stop calling API and ask deep clarification.
```

---

## Feature: Guardrail Layer

File `app/core/guardrail.py` — chạy sau mỗi vòng lặp

| Guardrail | Điều kiện | Hành động |
|-----------|-----------|-----------|
| **Zero Result** | Places API trả `ZERO_RESULTS` | Thông báo, đề xuất mở rộng bán kính |
| **Max Retries** | User từ chối ≥ 3 lần | Dừng API, hỏi sâu |
| **Ambiguous Location** | Geocoding confidence < 0.7 | Bắt buộc user xác nhận |
| **Midnight Filter** | Giờ 22:00–05:00 | Ưu tiên `open_now: true` |
| **Anti-hallucination** | Agent tự bịa tên quán | Mọi quán phải có `place_id` hợp lệ |

```python
def run_guardrails(state: AgentState) -> AgentState:
    # 1. Zero Result check
    if state.places and len(state.places) == 0:
        state.messages.append("Không tìm thấy quán. Bạn muốn tăng bán kính không?")

    # 2. Max Retries check
    if state.rejection_count >= 3:
        state.should_expand_search = False
        state.messages.append("Bạn có thể cho tôi biết thêm về sở thích không? (không gian, ngân sách)")

    # 3. Midnight filter
    if is_midnight():
        state.open_now_override = True

    return state
```

---

## Dependencies

- **Uses:** `app/tools/` (gọi các tool)
- **Called by:** `app/api/chat.py` (WebSocket handler)
- **External:** `langgraph`, `litellm`

---

## Files to Create

```
app/agent/
├── __init__.py
├── state.py         # AgentState TypedDict
├── graph.py         # LangGraph compilation
├── nodes.py         # think_node, act_node, observe_node
├── prompt.py        # System prompt
└── runner.py        # Entry point cho chat
app/core/
└── guardrail.py    # Guardrail rules
```

---

## Checklist

- [ ] `app/agent/state.py` - Define AgentState
- [ ] `app/agent/nodes.py` - think, act, observe nodes
- [ ] `app/agent/graph.py` - Compile LangGraph
- [ ] `app/agent/prompt.py` - System prompt
- [ ] `app/agent/runner.py` - Run agent cho một session
- [ ] `app/core/guardrail.py` - All guardrail rules
- [ ] Unit tests cho guardrails
