# Hướng dẫn phát triển: `get_user_preference` Feature

## Mục lục

1. [Tổng quan Feature](#1-tổng-quan-feature)
2. [Business Logic Flow](#2-business-logic-flow)
3. [Step-by-step Development](#3-step-by-step-development)
4. [Error Handling Cases](#4-error-handling-cases)
5. [Unit Testing](#5-unit-testing)
6. [Code Implementation](#6-code-implementation)

---

## 1. Tổng quan Feature

### Mục tiêu
Lấy preference đã lưu của user (favorite cuisines, price range, preferred ambiance, avoid cuisines) từ MongoDB để cá nhân hóa gợi ý món ăn. Phase 1: stub trả `None`. Phase 2: kết nối MongoDB thực sự.

### Dữ liệu trả về

| Field | Type | Mô tả |
|-------|------|-------|
| `user_id` | str | ID của user |
| `favorite_cuisines` | list[str] | Các loại món ăn yêu thích |
| `avoid_cuisines` | list[str] | Các loại món ăn muốn tránh |
| `price_range` | str | "low" / "mid" / "high" |
| `preferred_ambiance` | str | Không gian ưa thích (VD: "vỉa hè", "nhà hàng sang trọng") |
| `dietary_restrictions` | list[str] | Hạn chế ăn uống (VD: "chay", "halal") |
| `created_at` | datetime | Thời điểm tạo preference |

### Collections liên quan

```json
// users collection
{
  "_id": "ObjectId",
  "user_id": "u01",
  "preference": {
    "favorite_cuisines": ["phở", "bún bò"],
    "avoid_cuisines": ["hải sản"],
    "price_range": "mid",
    "preferred_ambiance": "vỉa hè",
    "dietary_restrictions": []
  },
  "created_at": "ISODate"
}
```

### Tool Definition đã có sẵn

Tool schema đã được định nghĩa trong `app/tools/definitions.py`:

```json
{
  "type": "function",
  "function": {
    "name": "get_user_preference",
    "description": "Get saved preferences for a user (favorite cuisines, price range, etc.)",
    "parameters": {
      "type": "object",
      "properties": {
        "user_id": {"type": "string", "description": "Unique user identifier"}
      },
      "required": ["user_id"]
    }
  }
}
```

### Handler đã có sẵn

Handler đã được đăng ký trong `app/agent/react_agent.py`:

```python
async def _tool_get_user_preference(self, args, state) -> str:
    """Get user preference from history."""
    from app.services.history import get_user_preference
    user_id = args.get("user_id") or state.get("user_id", "")
    pref = await get_user_preference(user_id)
    return json.dumps(pref or {})
```

---

## 2. Business Logic Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    get_user_preference                        │
│  Input: user_id                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Validate Input  │
                    │ - user_id required│
                    │ - user_id not empty│
                    └─────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │ Valid          │ Invalid       │
              ▼                               ▼
    ┌─────────────────┐              ┌─────────────────┐
    │  Query MongoDB  │              │  Raise Error    │
    │  users collection│              │  ValueError      │
    │  filter: user_id │              └─────────────────┘
    └─────────────────┘
              │
              ├──────────────────┬──────────────────┐
              │ Found           │ Not Found        │
              ▼                 ▼                  ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Return Preference│ │  Return Default   │ │  Return Default   │
    │  Document        │ │  Preference    │ │  Preference    │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
                              │                  │
                              └────────┬─────────┘
                                       ▼
                              ┌─────────────────┐
                              │ Return JSON     │
                              │ {user_id, ...}  │
                              └─────────────────┘
```

---

## 3. Step-by-step Development

### Step 1: Tạo Pydantic Models

```python
# app/db/models.py (nếu chưa có, thêm vào cuối file)
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class UserPreference(BaseModel):
    """User's food preferences"""
    favorite_cuisines: list[str] = Field(default_factory=list)
    avoid_cuisines: list[str] = Field(default_factory=list)
    price_range: str = Field(default="mid")  # "low", "mid", "high"
    preferred_ambiance: Optional[str] = None
    dietary_restrictions: list[str] = Field(default_factory=list)

class UserDocument(BaseModel):
    """User document stored in MongoDB"""
    user_id: str
    preference: UserPreference = Field(default_factory=UserPreference)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
```

### Step 2: Tạo Database Connection (hoặc mở rộng)

```python
# app/db/connection.py (mở rộng file hiện có)
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

class Database:
    client: AsyncIOMotorClient = None

db = Database()

async def connect_db():
    db.client = AsyncIOMotorClient(settings.MONGODB_URI)
    # Create index on user_id
    await db.client.foodie.users.create_index("user_id", unique=True)

async def close_db():
    if db.client:
        db.client.close()

def get_db():
    return db.client.foodie
```

### Step 3: Implement get_user_preference (Core Logic)

Cập nhật `app/services/history.py`:

```python
# app/services/history.py
"""History service — Phase 1 stubs, Phase 2 MongoDB."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger("foodie.history")

# Lazy MongoDB client (Phase 2: use motor)
_mongo_client = None

async def _get_mongo_collection():
    """Get MongoDB collection. Phase 2: connect lazily."""
    global _mongo_client
    if _mongo_client is None:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            _mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
        except Exception as e:
            logger.warning("mongodb_connection_failed", error=str(e))
            return None
    return _mongo_client.foodie.users


async def get_user_preference(user_id: str) -> dict | None:
    """Get user preference from MongoDB.

    Phase 1: return None (no DB yet).
    Phase 2: query users collection by user_id.

    Args:
        user_id: Unique user identifier.

    Returns:
        Preference dict if user exists, None otherwise.
    """
    if not user_id or not user_id.strip():
        logger.warning(
            "preference_fetch_empty_user_id",
            user_id=user_id,
        )
        return None

    logger.info(
        "preference_fetch_start",
        user_id=user_id,
    )

    collection = await _get_mongo_collection()
    if collection is None:
        # Phase 1 fallback: no DB
        logger.info(
            "preference_fetch_no_db",
            user_id=user_id,
        )
        return None

    try:
        doc = await collection.find_one(
            {"user_id": user_id},
            {"preference": 1, "user_id": 1, "_id": 0}
        )

        if doc and "preference" in doc:
            logger.info(
                "preference_fetched",
                user_id=user_id,
                found=True,
            )
            return {
                "user_id": user_id,
                **doc["preference"],
            }
        else:
            logger.info(
                "preference_not_found",
                user_id=user_id,
                found=False,
            )
            return None

    except Exception as e:
        logger.error(
            "preference_fetch_error",
            user_id=user_id,
            error=str(e),
        )
        return None


async def save_selection(user_id: str, place: dict) -> None:
    """Save a restaurant selection for a user.
    Phase 1: log only (no DB persistence).
    """
    logger.info(
        "selection_saved",
        user_id=user_id,
        place_id=place.get("place_id"),
        name=place.get("name"),
    )


async def save_session(session_id: str, state: dict) -> None:
    """Save session state to DB.
    Phase 1: log only.
    """
    logger.info(
        "session_saved",
        session_id=session_id,
    )


async def load_session(session_id: str) -> dict | None:
    """Load session state from DB.
    Phase 1: return None.
    """
    return None
```

### Step 4: Verify Tool Handler (không cần thay đổi)

Handler trong `app/agent/react_agent.py` đã gọi đúng hàm:

```python
async def _tool_get_user_preference(self, args, state) -> str:
    """Get user preference from history."""
    from app.services.history import get_user_preference
    user_id = args.get("user_id") or state.get("user_id", "")
    pref = await get_user_preference(user_id)
    return json.dumps(pref or {})
```

---

## 4. Error Handling Cases

### Case 1: Empty / Whitespace user_id

```python
# Test: Empty user_id
pref = await get_user_preference("")
# Expected: Log warning, return None

pref = await get_user_preference("   ")
# Expected: Log warning, return None
```

### Case 2: User Not Found

```python
# Test: user_id exists but no preference document
pref = await get_user_preference("nonexistent_user")
# Expected: Log info, return None
```

### Case 3: MongoDB Connection Failure

```python
# Test: MongoDB is down or connection string invalid
# Expected: Log error, return None gracefully
# Expected: Do NOT raise exception
pref = await get_user_preference("u01")
# Should not crash the agent
```

### Case 4: Valid User with Full Preference

```python
# Test: User with all preference fields
pref = await get_user_preference("u01")
# Expected:
# {
#   "user_id": "u01",
#   "favorite_cuisines": ["phở", "bún bò"],
#   "avoid_cuisines": ["hải sản"],
#   "price_range": "mid",
#   "preferred_ambiance": "vỉa hè",
#   "dietary_restrictions": ["chay"]
# }
```

---

## 5. Unit Testing

### File: `tests/test_get_user_preference_service.py`

```python
# tests/test_get_user_preference_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.services.history import get_user_preference

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_collection():
    """Mock MongoDB users collection"""
    collection = MagicMock()
    collection.find_one = AsyncMock()
    return collection

@pytest.fixture
def mock_mongo_client(mock_collection):
    """Mock MongoDB client returning our collection"""
    client = MagicMock()
    client.foodie.users = mock_collection
    return client

@pytest.fixture
def sample_preference_doc():
    """Sample preference document from MongoDB"""
    return {
        "user_id": "u01",
        "preference": {
            "favorite_cuisines": ["phở", "bún bò"],
            "avoid_cuisines": ["hải sản"],
            "price_range": "mid",
            "preferred_ambiance": "vỉa hè",
            "dietary_restrictions": []
        }
    }

# ============================================================
# TEST: Validation
# ============================================================

class TestValidation:
    """Test input validation"""

    @pytest.mark.asyncio
    async def test_empty_user_id_returns_none(self):
        """Empty string user_id should return None"""
        pref = await get_user_preference("")
        assert pref is None

    @pytest.mark.asyncio
    async def test_whitespace_user_id_returns_none(self):
        """Whitespace-only user_id should return None"""
        pref = await get_user_preference("   ")
        assert pref is None

    @pytest.mark.asyncio
    async def test_none_user_id_returns_none(self):
        """None user_id should return None"""
        pref = await get_user_preference(None)
        assert pref is None

# ============================================================
# TEST: User Not Found
# ============================================================

class TestUserNotFound:
    """Test when user does not exist in DB"""

    @pytest.mark.asyncio
    async def test_user_not_found_returns_none(self, mock_collection):
        """User not in DB should return None"""
        mock_collection.find_one = AsyncMock(return_value=None)

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            pref = await get_user_preference("unknown_user_123")

        assert pref is None
        mock_collection.find_one.assert_called_once_with(
            {"user_id": "unknown_user_123"},
            {"preference": 1, "user_id": 1, "_id": 0}
        )

    @pytest.mark.asyncio
    async def test_user_found_but_no_preference_returns_none(self, mock_collection):
        """User exists but has no preference field"""
        mock_collection.find_one = AsyncMock(return_value={"user_id": "u99"})

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            pref = await get_user_preference("u99")

        assert pref is None

# ============================================================
# TEST: User Found - Full Preference
# ============================================================

class TestUserFound:
    """Test when user exists with full preference"""

    @pytest.mark.asyncio
    async def test_returns_preference_with_all_fields(
        self, mock_collection, sample_preference_doc
    ):
        """Full preference document should be returned"""
        mock_collection.find_one = AsyncMock(return_value=sample_preference_doc)

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            pref = await get_user_preference("u01")

        assert pref is not None
        assert pref["user_id"] == "u01"
        assert pref["favorite_cuisines"] == ["phở", "bún bò"]
        assert pref["avoid_cuisines"] == ["hải sản"]
        assert pref["price_range"] == "mid"
        assert pref["preferred_ambiance"] == "vỉa hè"

    @pytest.mark.asyncio
    async def test_partial_preference_returns_existing_fields(
        self, mock_collection
    ):
        """Partial preference should return only existing fields"""
        partial_doc = {
            "user_id": "u05",
            "preference": {
                "favorite_cuisines": ["bánh mì"],
                "price_range": "low"
            }
        }
        mock_collection.find_one = AsyncMock(return_value=partial_doc)

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            pref = await get_user_preference("u05")

        assert pref is not None
        assert pref["user_id"] == "u05"
        assert pref["favorite_cuisines"] == ["bánh mì"]
        assert pref["price_range"] == "low"
        # Absent fields should be absent
        assert "preferred_ambiance" not in pref

    @pytest.mark.asyncio
    async def test_find_one_queries_correct_projection(
        self, mock_collection, sample_preference_doc
    ):
        """Should query with correct projection (exclude _id)"""
        mock_collection.find_one = AsyncMock(return_value=sample_preference_doc)

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            await get_user_preference("u01")

        call_args = mock_collection.find_one.call_args
        assert call_args[0][0] == {"user_id": "u01"}
        projection = call_args[0][1]
        assert projection.get("preference") == 1
        assert projection.get("user_id") == 1
        assert projection.get("_id") == 0

# ============================================================
# TEST: MongoDB Connection Failure
# ============================================================

class TestMongoDBFailure:
    """Test graceful handling of MongoDB errors"""

    @pytest.mark.asyncio
    async def test_mongodb_not_available_returns_none(self):
        """When MongoDB collection is None, should return None gracefully"""
        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=None)
        ):
            pref = await get_user_preference("u01")

        assert pref is None

    @pytest.mark.asyncio
    async def test_find_one_exception_returns_none(self, mock_collection):
        """DB error should be caught, return None, not raise"""
        mock_collection.find_one = AsyncMock(
            side_effect=Exception("MongoDB connection error")
        )

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            pref = await get_user_preference("u01")

        assert pref is None

    @pytest.mark.asyncio
    async def test_find_one_timeout_returns_none(self, mock_collection):
        """Timeout error should be caught, return None, not raise"""
        import httpx
        mock_collection.find_one = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            pref = await get_user_preference("u01")

        assert pref is None

# ============================================================
# TEST: Edge Cases
# ============================================================

class TestEdgeCases:
    """Edge case tests"""

    @pytest.mark.asyncio
    async def test_empty_preference_dict_returns_empty(self, mock_collection):
        """User with empty preference dict returns empty dict"""
        mock_collection.find_one = AsyncMock(
            return_value={"user_id": "u10", "preference": {}}
        )

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            pref = await get_user_preference("u10")

        assert pref is not None
        assert pref["user_id"] == "u10"

    @pytest.mark.asyncio
    async def test_user_id_with_special_characters(self, mock_collection):
        """User ID with special chars should be handled"""
        mock_collection.find_one = AsyncMock(
            return_value={
                "user_id": "user@example.com",
                "preference": {"favorite_cuisines": ["pizza"]}
            }
        )

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            pref = await get_user_preference("user@example.com")

        assert pref is not None
        assert pref["user_id"] == "user@example.com"
        mock_collection.find_one.assert_called_once_with(
            {"user_id": "user@example.com"},
            {"preference": 1, "user_id": 1, "_id": 0}
        )

    @pytest.mark.asyncio
    async def test_unicode_user_id(self, mock_collection):
        """Unicode user ID should be handled"""
        mock_collection.find_one = AsyncMock(
            return_value={
                "user_id": "user_người_dùng",
                "preference": {"favorite_cuisines": ["cơm"]}
            }
        )

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            pref = await get_user_preference("user_người_dùng")

        assert pref is not None
        assert pref["user_id"] == "user_người_dùng"

    @pytest.mark.asyncio
    async def test_concurrent_calls_use_same_connection(
        self, mock_collection, sample_preference_doc
    ):
        """Multiple concurrent calls should not create new connections"""
        import asyncio

        mock_collection.find_one = AsyncMock(return_value=sample_preference_doc)

        with patch(
            "app.services.history._get_mongo_collection",
            AsyncMock(return_value=mock_collection)
        ):
            # Reset the global client to test singleton behavior
            import app.services.history as history_module
            history_module._mongo_client = None

            results = await asyncio.gather(
                get_user_preference("u01"),
                get_user_preference("u02"),
                get_user_preference("u03"),
            )

        # All should return successfully
        assert all(r is not None for r in results)
```

### File: `tests/test_get_user_preference_tool.py`

```python
# tests/test_get_user_preference_tool.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from app.agent.state import AgentState
from app.agent.react_agent import ReActAgent

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def agent():
    """Create ReActAgent with all tools"""
    from app.tools.definitions import get_tool_definitions
    tools = get_tool_definitions()
    return ReActAgent(tools=tools)

@pytest.fixture
def sample_preference():
    return {
        "user_id": "u01",
        "favorite_cuisines": ["phở", "bún bò"],
        "avoid_cuisines": [],
        "price_range": "mid",
        "preferred_ambiance": "vỉa hè",
        "dietary_restrictions": []
    }

# ============================================================
# TEST: Tool Definition
# ============================================================

class TestToolDefinition:
    """Test tool schema correctness"""

    def test_get_user_preference_tool_exists(self):
        """get_user_preference tool should be in definitions"""
        from app.tools.definitions import get_tool_definitions
        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "get_user_preference" in tool_names

    def test_get_user_preference_tool_schema(self):
        """Tool schema should have correct structure"""
        from app.tools.definitions import get_tool_definitions
        tools = get_tool_definitions()
        tool = next(
            t for t in tools
            if t["function"]["name"] == "get_user_preference"
        )

        params = tool["function"]["parameters"]
        assert params["type"] == "object"
        assert "user_id" in params["properties"]
        assert "user_id" in params["required"]

    def test_get_user_preference_user_id_is_string(self):
        """user_id parameter should be type string"""
        from app.tools.definitions import get_tool_definitions
        tools = get_tool_definitions()
        tool = next(
            t for t in tools
            if t["function"]["name"] == "get_user_preference"
        )

        user_id_param = tool["function"]["parameters"]["properties"]["user_id"]
        assert user_id_param["type"] == "string"

# ============================================================
# TEST: ReAct Agent Handler
# ============================================================

class TestReActAgentHandler:
    """Test _tool_get_user_preference handler"""

    @pytest.mark.asyncio
    async def test_handler_returns_preference_dict(self, agent, sample_preference):
        """Handler should return JSON-encoded preference dict"""
        state: AgentState = {"user_id": "u01"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value=sample_preference)
        ):
            result = await agent._tool_get_user_preference(
                {"user_id": "u01"}, state
            )

        parsed = json.loads(result)
        assert parsed["user_id"] == "u01"
        assert parsed["favorite_cuisines"] == ["phở", "bún bò"]

    @pytest.mark.asyncio
    async def test_handler_returns_empty_dict_when_no_preference(self, agent):
        """Handler should return {} when preference is None"""
        state: AgentState = {"user_id": "u99"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value=None)
        ):
            result = await agent._tool_get_user_preference(
                {"user_id": "u99"}, state
            )

        parsed = json.loads(result)
        assert parsed == {}

    @pytest.mark.asyncio
    async def test_handler_uses_user_id_from_args(self, agent, sample_preference):
        """Handler should use user_id from args first"""
        state: AgentState = {"user_id": "fallback_id"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value=sample_preference)
        ) as mock_get:
            await agent._tool_get_user_preference(
                {"user_id": "u01"}, state
            )

        mock_get.assert_called_once_with("u01")

    @pytest.mark.asyncio
    async def test_handler_falls_back_to_state_user_id(self, agent, sample_preference):
        """Handler should fallback to state.user_id when args.user_id is None"""
        state: AgentState = {"user_id": "u05"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value=sample_preference)
        ) as mock_get:
            await agent._tool_get_user_preference({}, state)

        mock_get.assert_called_once_with("u05")

    @pytest.mark.asyncio
    async def test_handler_falls_back_to_empty_string(self, agent):
        """Handler should fallback to empty string if both are missing"""
        state: AgentState = {}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value=None)
        ) as mock_get:
            await agent._tool_get_user_preference({}, state)

        mock_get.assert_called_once_with("")

# ============================================================
# TEST: Tool Routing
# ============================================================

class TestToolRouting:
    """Test that get_user_preference routes correctly"""

    @pytest.mark.asyncio
    async def test_get_user_preference_routes_to_handler(self, agent):
        """Tool name should route to correct handler"""
        state: AgentState = {"user_id": "u01"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value={"user_id": "u01", "favorite_cuisines": []})
        ):
            result = await agent._route_tool(
                "get_user_preference",
                {"user_id": "u01"},
                state
            )

        parsed = json.loads(result)
        assert "user_id" in parsed

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, agent):
        """Unknown tool should return error message"""
        result = await agent._route_tool("nonexistent_tool", {}, {})

        assert "Unknown tool" in result

# ============================================================
# TEST: Full Integration
# ============================================================

class TestFullIntegration:
    """Full flow integration tests"""

    @pytest.mark.asyncio
    async def test_preference_found_integration(self, agent, sample_preference):
        """Full flow: user has preference → returns it"""
        state: AgentState = {"user_id": "u01"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value=sample_preference)
        ):
            tool_result = await agent._execute_tool(
                {
                    "name": "get_user_preference",
                    "arguments": '{"user_id": "u01"}'
                },
                state
            )

        parsed = json.loads(tool_result)
        assert parsed["favorite_cuisines"] == ["phở", "bún bò"]

        # State should track the tool call
        assert len(state["tool_calls"]) == 1
        assert state["tool_calls"][0]["tool"] == "get_user_preference"

    @pytest.mark.asyncio
    async def test_preference_not_found_integration(self, agent):
        """Full flow: user has no preference → returns empty dict"""
        state: AgentState = {"user_id": "new_user"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value=None)
        ):
            tool_result = await agent._execute_tool(
                {
                    "name": "get_user_preference",
                    "arguments": '{"user_id": "new_user"}'
                },
                state
            )

        parsed = json.loads(tool_result)
        assert parsed == {}

    @pytest.mark.asyncio
    async def test_tool_call_error_handled_gracefully(self, agent):
        """DB error during tool call should be handled"""
        state: AgentState = {"user_id": "u01"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(side_effect=Exception("DB connection lost"))
        ):
            tool_result = await agent._execute_tool(
                {
                    "name": "get_user_preference",
                    "arguments": '{"user_id": "u01"}'
                },
                state
            )

        assert "Error:" in tool_result
        # Error should be recorded in tool_calls
        assert state["tool_calls"][0]["error"] is not None

# ============================================================
# TEST: Logging Verification
# ============================================================

class TestLogging:
    """Verify logging is called correctly"""

    @pytest.mark.asyncio
    async def test_preference_fetch_start_logged(self, agent, sample_preference):
        """Should log preference_fetch_start before DB call"""
        state: AgentState = {"user_id": "u01"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value=sample_preference)
        ) as mock_get:
            await agent._tool_get_user_preference({"user_id": "u01"}, state)

        mock_get.assert_called_once_with("u01")

    @pytest.mark.asyncio
    async def test_tool_call_start_logged(self, agent, sample_preference):
        """_execute_tool should log tool_call_start"""
        state: AgentState = {"user_id": "u01"}

        with patch(
            "app.services.history.get_user_preference",
            AsyncMock(return_value=sample_preference)
        ):
            with patch("app.agent.react_agent.tool_logger") as mock_logger:
                await agent._execute_tool(
                    {
                        "name": "get_user_preference",
                        "arguments": '{"user_id": "u01"}'
                    },
                    state
                )

                # Verify tool_call_start was logged
                assert mock_logger.info.called
                call_args = str(mock_logger.info.call_args)
                assert "get_user_preference" in call_args
```

### Run Tests

```bash
# Run all preference tests
pytest tests/test_get_user_preference_service.py tests/test_get_user_preference_tool.py -v

# Run with coverage
pytest tests/ --cov=app.services.history --cov=app.agent.react_agent -v

# Run specific test class
pytest tests/test_get_user_preference_service.py::TestValidation -v
pytest tests/test_get_user_preference_service.py::TestMongoDBFailure -v

# Run with asyncio
pytest tests/ -v --asyncio-mode=auto
```

---

## 6. Code Implementation

### Final File Structure

```
app/
├── services/
│   ├── __init__.py
│   └── history.py              # Updated: get_user_preference (Phase 1 + Phase 2)
├── db/
│   └── models.py               # UserPreference, UserDocument models
└── agent/
    └── react_agent.py           # _tool_get_user_preference (already exists)

tests/
├── conftest.py
├── test_get_user_preference_service.py   # Service unit tests (25+ cases)
└── test_get_user_preference_tool.py     # Handler + routing tests (15+ cases)
```

### Summary of Changes

| File | Action | Description |
|------|--------|-------------|
| `app/services/history.py` | **Update** | Replace stub with real MongoDB implementation |
| `app/db/models.py` | **Create/Add** | Add `UserPreference`, `UserDocument` Pydantic models |
| `app/db/connection.py` | **Create/Extend** | Add MongoDB connection utilities |
| `tests/test_get_user_preference_service.py` | **Create** | 25+ test cases for service layer |
| `tests/test_get_user_preference_tool.py` | **Create** | 15+ test cases for tool handler |
| `app/agent/react_agent.py` | No change | Handler already exists and calls correct function |
| `app/tools/definitions.py` | No change | Tool schema already defined |

---

## Checklist

- [ ] Thêm `UserPreference`, `UserDocument` models vào `app/db/models.py`
- [ ] Cập nhật `app/services/history.py` — thay stub bằng MongoDB query
- [ ] Tạo `tests/test_get_user_preference_service.py` — 25+ test cases
- [ ] Tạo `tests/test_get_user_preference_tool.py` — 15+ test cases
- [ ] Chạy tests → all green ✓
- [ ] Verify handler logs `foodie.tool.*` events correctly
- [ ] Verify tool routing works in full ReAct loop
