# Hướng dẫn phát triển: `save_user_selection` Feature

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
Lưu quán ăn user đã chọn vào lịch sử, đồng thời cập nhật preference của user để cá nhân hóa gợi ý về sau.

### Dữ liệu lưu trữ

| Field | Type | Mô tả |
|-------|------|-------|
| `user_id` | str | ID của user |
| `place_id` | str | Google Places ID (unique) |
| `name` | str | Tên quán ăn |
| `cuisine_type` | str | Loại món ăn (VD: "phở", "bún bò") |
| `rating` | float | Rating từ Google (0.0 - 5.0) |
| `selected_at` | datetime | Thời điểm user chọn |

### Side Effects
- Cập nhật `favorite_cuisines` trong `User.preference` nếu user chọn quán mới
- Tăng count nếu cuisine đã có trong favorites

### Collections liên quan

```json
// selections collection
{
  "_id": "ObjectId",
  "user_id": "u01",
  "place_id": "ChIJ...",
  "name": "Phở Thìn",
  "cuisine_type": "phở",
  "rating": 4.5,
  "selected_at": "ISODate"
}

// users collection (preference update)
{
  "_id": "ObjectId",
  "user_id": "u01",
  "preference": {
    "favorite_cuisines": ["phở", "bún bò"],
    "avoid_cuisines": [],
    "price_range": "mid",
    "preferred_ambiance": "vỉa hè"
  }
}
```

---

## 2. Business Logic Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  save_user_selection                        │
│  Input: user_id, place_id, name, cuisine_type, rating     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Validate Input  │
                    │ - user_id required│
                    │ - place_id unique │
                    │ - rating 0.0-5.0 │
                    └─────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │ Valid          │ Invalid       │
              ▼                               ▼
    ┌─────────────────┐              ┌─────────────────┐
    │ Check Duplicate │              │  Raise Error    │
    │ place_id exists?│              │  ValidationErr  │
    └─────────────────┘              └─────────────────┘
              │
              ├──────────────────┬──────────────────┐
              │ Yes             │ No                │
              ▼                 ▼                    ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Update Existing │ │  Insert New      │ │  Insert New     │
    │  selection       │ │  selection       │ │  selection      │
    │  (update_at)     │ │  (selected_at)   │ │                 │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
              │                 │                    │
              └────────┬────────┴────────────────────┘
                       ▼
              ┌─────────────────┐
              │ Update User     │
              │ Preference      │
              │ - Add cuisine   │
              │   to favorites  │
              │ - Update count  │
              └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Return Result   │
              │ Selection saved  │
              │ preference updated│
              └─────────────────┘
```

---

## 3. Step-by-step Development

### Step 1: Tạo Model Definitions

```python
# app/db/models.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class Selection(BaseModel):
    """Model for user's restaurant selection"""
    user_id: str = Field(..., description="User ID")
    place_id: str = Field(..., description="Google Places ID")
    name: str = Field(..., description="Restaurant name")
    cuisine_type: Optional[str] = Field(None, description="Cuisine type")
    rating: float = Field(..., ge=0.0, le=5.0, description="Rating 0.0-5.0")
    selected_at: datetime = Field(default_factory=datetime.utcnow)

class SelectionResponse(BaseModel):
    """Response after saving selection"""
    success: bool
    message: str
    selection: Selection
    preference_updated: bool = False

class UserPreference(BaseModel):
    """User's food preferences"""
    favorite_cuisines: list[str] = Field(default_factory=list)
    avoid_cuisines: list[str] = Field(default_factory=list)
    price_range: str = Field(default="mid")  # "low", "mid", "high"
    preferred_ambiance: Optional[str] = None

class CuisineCount(BaseModel):
    """Track cuisine selection count for ranking"""
    cuisine: str
    count: int = 1
    last_selected: datetime = Field(default_factory=datetime.utcnow)
```

### Step 2: Tạo Database Connection

```python
# app/db/connection.py
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

class Database:
    client: AsyncIOMotorClient = None

db = Database()

async def connect_db():
    db.client = AsyncIOMotorClient(settings.MONGODB_URI)
    # Create indexes
    await db.client.foodie.users.create_index("user_id", unique=True)
    await db.client.foodie.selections.create_index("user_id")
    await db.client.foodie.selections.create_index("place_id")
    await db.client.foodie.selections.create_index(
        [("user_id", 1), ("place_id", 1)],
        unique=True  # Prevent duplicate selections
    )

async def close_db():
    db.client.close()

def get_db():
    return db.client.foodie
```

### Step 3: Tạo Preference Service

```python
# app/services/preference_service.py
from datetime import datetime
from typing import Optional
from app.db.connection import get_db
from app.db.models import UserPreference, CuisineCount

class PreferenceService:
    """Service for managing user preferences"""

    async def get_preference(self, user_id: str) -> UserPreference:
        """Get user's preference, return default if not exists"""
        doc = await get_db().users.find_one(
            {"user_id": user_id},
            {"preference": 1}
        )

        if doc and "preference" in doc:
            return UserPreference(**doc["preference"])

        return UserPreference()

    async def add_favorite_cuisine(
        self,
        user_id: str,
        cuisine: str,
        increment_count: bool = True
    ) -> UserPreference:
        """
        Add cuisine to user's favorites.
        If cuisine exists, increment its count.
        If not, add new cuisine.
        """
        db = get_db()

        if increment_count:
            # Update existing cuisine count
            result = await db.users.update_one(
                {
                    "user_id": user_id,
                    "preference.favorite_cuisines": cuisine
                },
                {
                    "$inc": {"preference.$[elem].count": 1},
                    "$set": {"preference.$[elem].last_selected": datetime.utcnow()}
                },
                array_filters=[{"elem.name": {"$eq": cuisine}}]
            )

            # If cuisine not in list, add it
            if result.modified_count == 0:
                await db.users.update_one(
                    {"user_id": user_id},
                    {
                        "$push": {
                            "preference.favorite_cuisines": {
                                "name": cuisine,
                                "count": 1,
                                "last_selected": datetime.utcnow()
                            }
                        }
                    }
                )
        else:
            # Just add cuisine without count
            result = await db.users.update_one(
                {"user_id": user_id},
                {
                    "$addToSet": {
                        "preference.favorite_cuisines": cuisine
                    }
                }
            )

        return await self.get_preference(user_id)

    async def increment_cuisine_count(
        self,
        user_id: str,
        cuisine: str
    ) -> bool:
        """
        Increment the count for a cuisine when user selects it.
        Returns True if cuisine exists and was updated.
        Returns False if cuisine is new (needs to be added).
        """
        result = await get_db().users.update_one(
            {
                "user_id": user_id,
                "preference.favorite_cuisines.name": cuisine
            },
            {
                "$inc": {"preference.favorite_cuisines.$.count": 1},
                "$set": {"preference.favorite_cuisines.$.last_selected": datetime.utcnow()}
            }
        )

        return result.modified_count > 0

    async def ensure_user_exists(self, user_id: str) -> None:
        """Create user document if not exists"""
        await get_db().users.update_one(
            {"user_id": user_id},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "preference": UserPreference().model_dump(),
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
```

### Step 4: Implement Selection Service (Core Logic)

```python
# app/services/selection_service.py
from datetime import datetime
from typing import Optional
from app.db.connection import get_db
from app.db.models import Selection, SelectionResponse
from app.services.preference_service import PreferenceService

class SelectionError(Exception):
    """Custom exception for selection errors"""
    pass

class DuplicateSelectionError(SelectionError):
    """Raised when trying to save duplicate selection"""
    pass

class SelectionService:
    """Service for managing user selections"""

    def __init__(self):
        self.preference_service = PreferenceService()

    async def save_selection(
        self,
        user_id: str,
        place_id: str,
        name: str,
        cuisine_type: Optional[str] = None,
        rating: float = 0.0,
        update_preference: bool = True
    ) -> SelectionResponse:
        """
        Save user's restaurant selection.

        Args:
            user_id: User identifier
            place_id: Google Places ID
            name: Restaurant name
            cuisine_type: Type of cuisine (optional)
            rating: Restaurant rating (0.0 - 5.0)
            update_preference: Whether to update user preferences

        Returns:
            SelectionResponse with success status and details

        Raises:
            DuplicateSelectionError: If place_id already selected
            ValueError: If required fields are invalid
        """
        # === Validation ===
        if not user_id:
            raise ValueError("user_id is required")

        if not place_id:
            raise ValueError("place_id is required")

        if not name:
            raise ValueError("name is required")

        if not 0.0 <= rating <= 5.0:
            raise ValueError("rating must be between 0.0 and 5.0")

        # === Check for duplicate ===
        existing = await get_db().selections.find_one({
            "user_id": user_id,
            "place_id": place_id
        })

        selection = Selection(
            user_id=user_id,
            place_id=place_id,
            name=name,
            cuisine_type=cuisine_type,
            rating=rating,
            selected_at=datetime.utcnow()
        )

        preference_updated = False

        if existing:
            # === Update existing selection ===
            await get_db().selections.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "name": name,
                        "cuisine_type": cuisine_type,
                        "rating": rating,
                        "selected_at": selection.selected_at
                    }
                }
            )
            selection_dict = existing
            selection_dict.update(selection.model_dump())

        else:
            # === Insert new selection ===
            await get_db().selections.insert_one(selection.model_dump())
            selection_dict = selection.model_dump()

        # === Update user preference ===
        if update_preference and cuisine_type:
            try:
                await self.preference_service.ensure_user_exists(user_id)
                cuisine_existed = await self.preference_service.increment_cuisine_count(
                    user_id, cuisine_type
                )

                if not cuisine_existed:
                    # Add new cuisine to favorites
                    await self.preference_service.preference_service.add_favorite_cuisine(
                        user_id, cuisine_type, increment_count=False
                    )

                preference_updated = True

            except Exception as e:
                # Log error but don't fail the selection save
                # Preference update is secondary
                pass

        return SelectionResponse(
            success=True,
            message="Selection saved successfully",
            selection=Selection(**selection_dict),
            preference_updated=preference_updated
        )

    async def get_user_selections(
        self,
        user_id: str,
        limit: int = 20,
        skip: int = 0
    ) -> list[Selection]:
        """Get user's selection history, most recent first"""
        cursor = get_db().selections.find(
            {"user_id": user_id}
        ).sort("selected_at", -1).skip(skip).limit(limit)

        selections = []
        async for doc in cursor:
            selections.append(Selection(**doc))

        return selections

    async def check_selection_exists(
        self,
        user_id: str,
        place_id: str
    ) -> bool:
        """Check if user has already selected this place"""
        doc = await get_db().selections.find_one({
            "user_id": user_id,
            "place_id": place_id
        })
        return doc is not None

    async def get_selection_count(self, user_id: str) -> int:
        """Get total number of selections for a user"""
        return await get_db().selections.count_documents({"user_id": user_id})

    async def get_top_cuisines(
        self,
        user_id: str,
        limit: int = 5
    ) -> list[dict]:
        """Get user's most selected cuisines"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$cuisine_type",
                "count": {"$sum": 1},
                "avg_rating": {"$avg": "$rating"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]

        result = []
        async for doc in get_db().selections.aggregate(pipeline):
            result.append({
                "cuisine": doc["_id"],
                "count": doc["count"],
                "avg_rating": round(doc["avg_rating"], 1)
            })

        return result
```

### Step 5: Tạo Tool Wrapper (LangChain BaseTool)

```python
# app/tools/memory_tool.py (part - save_user_selection)
from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from app.services.selection_service import SelectionService

class SaveUserSelectionInput(BaseModel):
    user_id: str = Field(description="User ID")
    place_id: str = Field(description="Google Places ID of the restaurant")
    name: str = Field(description="Name of the restaurant")
    cuisine_type: Optional[str] = Field(None, description="Type of cuisine")
    rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Restaurant rating")

class SaveUserSelectionOutput(BaseModel):
    success: bool
    message: str
    selection_id: Optional[str] = None
    preference_updated: bool

class SaveUserSelectionTool(BaseTool):
    name = "save_user_selection"
    description = """
    Save a restaurant selection when user chooses a restaurant.
    This stores the selection in history and updates user preferences.

    Input:
    - user_id: User identifier (required)
    - place_id: Google Places ID (required)
    - name: Restaurant name (required)
    - cuisine_type: Type of cuisine (optional)
    - rating: Rating from 0.0 to 5.0 (optional, default 0.0)
    """
    args_schema: Type[BaseModel] = SaveUserSelectionInput
    selection_service: SelectionService = None

    def __init__(self, selection_service: SelectionService = None):
        super().__init__()
        self.selection_service = selection_service or SelectionService()

    async def _arun(
        self,
        user_id: str,
        place_id: str,
        name: str,
        cuisine_type: Optional[str] = None,
        rating: float = 0.0
    ) -> dict:
        response = await self.selection_service.save_selection(
            user_id=user_id,
            place_id=place_id,
            name=name,
            cuisine_type=cuisine_type,
            rating=rating
        )

        return {
            "success": response.success,
            "message": response.message,
            "preference_updated": response.preference_updated
        }

    def _run(
        self,
        user_id: str,
        place_id: str,
        name: str,
        cuisine_type: Optional[str] = None,
        rating: float = 0.0
    ) -> dict:
        """Sync wrapper"""
        import asyncio
        return asyncio.run(
            self._arun(user_id, place_id, name, cuisine_type, rating)
        )
```

---

## 4. Error Handling Cases

### Case 1: Missing Required Fields

```python
# Test: user_id is empty
with pytest.raises(ValueError, match="user_id is required"):
    await service.save_selection(
        user_id="",
        place_id="ChIJxxx",
        name="Phở Thìn"
    )
```

### Case 2: Invalid Rating

```python
# Test: rating out of range
with pytest.raises(ValueError, match="rating must be between"):
    await service.save_selection(
        user_id="u01",
        place_id="ChIJxxx",
        name="Phở Thìn",
        rating=6.0  # Invalid!
    )
```

### Case 3: Duplicate Selection (same place, same user)

```python
# Test: User selects same restaurant twice
# First selection - should succeed
result1 = await service.save_selection(
    user_id="u01",
    place_id="ChIJxxx",
    name="Phở Thìn",
    cuisine_type="phở",
    rating=4.5
)
assert result1.success

# Second selection (same place) - should update existing
result2 = await service.save_selection(
    user_id="u01",
    place_id="ChIJxxx",  # Same place!
    name="Phở Thìn Updated",
    cuisine_type="phở",
    rating=4.8
)
assert result2.success
assert result2.selection.selected_at > result1.selection.selected_at
```

### Case 4: User Doesn't Exist

```python
# Test: New user saves first selection
# Should auto-create user document
result = await service.save_selection(
    user_id="new_user_999",  # Doesn't exist in DB
    place_id="ChIJxxx",
    name="Quán Mới",
    cuisine_type="bánh mì"
)
assert result.success

# Verify user was created with preference
preference = await preference_service.get_preference("new_user_999")
assert preference is not None
```

### Case 5: Cuisine Added to Favorites

```python
# Test: First time user selects phở
result = await service.save_selection(
    user_id="u01",
    place_id="ChIJ_pho1",
    name="Phở Thìn",
    cuisine_type="phở"
)
assert result.preference_updated

# Verify cuisine is in favorites
preference = await preference_service.get_preference("u01")
cuisine_names = [c.get("name", c) if isinstance(c, dict) else c
                for c in preference.favorite_cuisines]
assert "phở" in cuisine_names
```

---

## 5. Unit Testing

### File: `tests/test_selection_service.py`

```python
# tests/test_selection_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.services.selection_service import (
    SelectionService,
    DuplicateSelectionError
)
from app.db.models import Selection, SelectionResponse

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def selection_service():
    """Create SelectionService with mocked dependencies"""
    service = SelectionService()
    service.preference_service = MagicMock()
    service.preference_service.ensure_user_exists = AsyncMock()
    service.preference_service.increment_cuisine_count = AsyncMock(return_value=False)
    service.preference_service.add_favorite_cuisine = AsyncMock()
    return service

@pytest.fixture
def sample_selection_data():
    return {
        "user_id": "u01",
        "place_id": "ChIJN1t tJFuEmsRmQ",
        "name": "Phở Thìn",
        "cuisine_type": "phở",
        "rating": 4.5
    }

@pytest.fixture
def mock_db():
    """Mock database operations"""
    mock = MagicMock()
    mock.find_one = AsyncMock(return_value=None)
    mock.insert_one = AsyncMock()
    mock.update_one = AsyncMock()
    mock.count_documents = AsyncMock(return_value=0)
    mock.aggregate = MagicMock(return_value=AsyncIteratorMock([]))
    return mock

# ============================================================
# TEST: Validation
# ============================================================

class TestValidation:
    """Test input validation"""

    @pytest.mark.asyncio
    async def test_missing_user_id_raises_error(self, selection_service):
        """Empty user_id should raise ValueError"""
        with pytest.raises(ValueError, match="user_id is required"):
            await selection_service.save_selection(
                user_id="",
                place_id="ChIJxxx",
                name="Test Restaurant"
            )

    @pytest.mark.asyncio
    async def test_missing_place_id_raises_error(self, selection_service):
        """Empty place_id should raise ValueError"""
        with pytest.raises(ValueError, match="place_id is required"):
            await selection_service.save_selection(
                user_id="u01",
                place_id="",
                name="Test Restaurant"
            )

    @pytest.mark.asyncio
    async def test_missing_name_raises_error(self, selection_service):
        """Empty name should raise ValueError"""
        with pytest.raises(ValueError, match="name is required"):
            await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name=""
            )

    @pytest.mark.asyncio
    async def test_rating_below_zero_raises_error(self, selection_service):
        """Rating < 0 should raise ValueError"""
        with pytest.raises(ValueError, match="rating must be between"):
            await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name="Test Restaurant",
                rating=-0.1
            )

    @pytest.mark.asyncio
    async def test_rating_above_five_raises_error(self, selection_service):
        """Rating > 5 should raise ValueError"""
        with pytest.raises(ValueError, match="rating must be between"):
            await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name="Test Restaurant",
                rating=5.5
            )

    @pytest.mark.parametrize("rating", [0.0, 1.0, 2.5, 4.0, 5.0])
    @pytest.mark.asyncio
    async def test_valid_ratings_accepted(self, selection_service, rating):
        """Ratings between 0.0 and 5.0 should be accepted"""
        with patch("app.services.selection_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()
            mock_get_db.return_value = mock_db

            result = await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name="Test Restaurant",
                rating=rating
            )

            assert result.success
            assert result.selection.rating == rating

# ============================================================
# TEST: New Selection (Insert)
# ============================================================

class TestNewSelection:
    """Test saving new selection"""

    @pytest.mark.asyncio
    async def test_save_new_selection_success(
        self, selection_service, sample_selection_data, mock_db
    ):
        """First selection for a place should insert successfully"""
        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()

            result = await selection_service.save_selection(**sample_selection_data)

            assert result.success
            assert result.message == "Selection saved successfully"
            assert result.selection.user_id == "u01"
            assert result.selection.name == "Phở Thìn"
            assert result.selection.cuisine_type == "phở"
            assert result.selection.rating == 4.5
            mock_db.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_selection_updates_preference(
        self, selection_service, sample_selection_data, mock_db
    ):
        """Saving selection should update user preference"""
        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()

            result = await selection_service.save_selection(**sample_selection_data)

            assert result.preference_updated
            selection_service.preference_service.ensure_user_exists.assert_called_once_with("u01")

    @pytest.mark.asyncio
    async def test_save_selection_without_cuisine_no_preference_update(
        self, selection_service, mock_db
    ):
        """Selection without cuisine should not update preference"""
        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()

            result = await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name="Unknown Restaurant",
                cuisine_type=None
            )

            assert result.success
            assert not result.preference_updated
            selection_service.preference_service.ensure_user_exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_selected_at_timestamp_is_set(
        self, selection_service, sample_selection_data, mock_db
    ):
        """selected_at should be set to current time"""
        before = datetime.utcnow()

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()

            result = await selection_service.save_selection(**sample_selection_data)

        after = datetime.utcnow()

        assert before <= result.selection.selected_at <= after

    @pytest.mark.asyncio
    async def test_disable_preference_update_flag(
        self, selection_service, sample_selection_data, mock_db
    ):
        """Setting update_preference=False should skip preference update"""
        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()

            result = await selection_service.save_selection(
                **sample_selection_data,
                update_preference=False
            )

            assert result.success
            assert not result.preference_updated

# ============================================================
# TEST: Duplicate Selection (Update)
# ============================================================

class TestDuplicateSelection:
    """Test when user selects the same place again"""

    @pytest.mark.asyncio
    async def test_duplicate_selection_updates_existing(
        self, selection_service, sample_selection_data, mock_db
    ):
        """Same place_id should update existing record, not create new"""
        existing_doc = {
            "_id": "existing_id",
            "user_id": "u01",
            "place_id": "ChIJN1t tJFuEmsRmQ",
            "name": "Phở Thìn Old",
            "cuisine_type": "phở",
            "rating": 4.0,
            "selected_at": datetime(2024, 1, 1)
        }

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=existing_doc)
            mock_db.update_one = AsyncMock()

            result = await selection_service.save_selection(**sample_selection_data)

            assert result.success
            mock_db.update_one.assert_called_once()
            mock_db.insert_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_updates_timestamp(
        self, selection_service, sample_selection_data, mock_db
    ):
        """Duplicate selection should update selected_at"""
        existing_doc = {
            "_id": "existing_id",
            "user_id": "u01",
            "place_id": "ChIJN1t tJFuEmsRmQ",
            "name": "Phở Thìn",
            "cuisine_type": "phở",
            "rating": 4.0,
            "selected_at": datetime(2024, 1, 1)
        }

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=existing_doc)
            mock_db.update_one = AsyncMock()

            result = await selection_service.save_selection(**sample_selection_data)

            # New timestamp should be different
            assert result.selection.selected_at > existing_doc["selected_at"]

    @pytest.mark.asyncio
    async def test_duplicate_updates_rating(
        self, selection_service, mock_db
    ):
        """Duplicate selection should update rating"""
        existing_doc = {
            "_id": "existing_id",
            "user_id": "u01",
            "place_id": "ChIJxxx",
            "name": "Phở Thìn",
            "cuisine_type": "phở",
            "rating": 4.0,
            "selected_at": datetime(2024, 1, 1)
        }

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=existing_doc)
            mock_db.update_one = AsyncMock()

            result = await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name="Phở Thìn",
                cuisine_type="phở",
                rating=4.8  # New rating
            )

            assert result.selection.rating == 4.8

# ============================================================
# TEST: Preference Update
# ============================================================

class TestPreferenceUpdate:
    """Test preference update logic"""

    @pytest.mark.asyncio
    async def test_new_cuisine_added_to_favorites(
        self, selection_service, sample_selection_data, mock_db
    ):
        """First time selecting a cuisine should add to favorites"""
        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()
            selection_service.preference_service.increment_cuisine_count = AsyncMock(
                return_value=False  # Cuisine doesn't exist
            )

            await selection_service.save_selection(**sample_selection_data)

            selection_service.preference_service.add_favorite_cuisine.assert_called_once_with(
                "u01", "phở", increment_count=False
            )

    @pytest.mark.asyncio
    async def test_existing_cuisine_increments_count(
        self, selection_service, sample_selection_data, mock_db
    ):
        """Selecting existing cuisine should increment count"""
        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()
            selection_service.preference_service.increment_cuisine_count = AsyncMock(
                return_value=True  # Cuisine exists
            )

            await selection_service.save_selection(**sample_selection_data)

            selection_service.preference_service.increment_cuisine_count.assert_called_once_with(
                "u01", "phở"
            )
            selection_service.preference_service.add_favorite_cuisine.assert_not_called()

    @pytest.mark.asyncio
    async def test_preference_error_doesnt_fail_selection(
        self, selection_service, sample_selection_data, mock_db
    ):
        """If preference update fails, selection should still save"""
        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()
            selection_service.preference_service.ensure_user_exists = AsyncMock(
                side_effect=Exception("DB Error")
            )

            result = await selection_service.save_selection(**sample_selection_data)

            # Selection should still succeed
            assert result.success
            assert not result.preference_updated

# ============================================================
# TEST: Helper Methods
# ============================================================

class TestHelperMethods:
    """Test helper methods"""

    @pytest.mark.asyncio
    async def test_check_selection_exists_true(self, selection_service, mock_db):
        """Should return True when selection exists"""
        mock_db.find_one = AsyncMock(return_value={"_id": "exists"})

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            exists = await selection_service.check_selection_exists("u01", "ChIJxxx")

            assert exists
            mock_db.find_one.assert_called_once_with({
                "user_id": "u01",
                "place_id": "ChIJxxx"
            })

    @pytest.mark.asyncio
    async def test_check_selection_exists_false(self, selection_service, mock_db):
        """Should return False when selection doesn't exist"""
        mock_db.find_one = AsyncMock(return_value=None)

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            exists = await selection_service.check_selection_exists("u01", "ChIJxxx")

            assert not exists

    @pytest.mark.asyncio
    async def test_get_selection_count(self, selection_service, mock_db):
        """Should return correct count"""
        mock_db.count_documents = AsyncMock(return_value=5)

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            count = await selection_service.get_selection_count("u01")

            assert count == 5
            mock_db.count_documents.assert_called_once_with({"user_id": "u01"})

    @pytest.mark.asyncio
    async def test_get_user_selections(self, selection_service, mock_db):
        """Should return sorted list of selections"""
        mock_docs = [
            {
                "user_id": "u01",
                "place_id": "ChIJ1",
                "name": "Restaurant 1",
                "cuisine_type": "phở",
                "rating": 4.5,
                "selected_at": datetime(2024, 1, 2)
            },
            {
                "user_id": "u01",
                "place_id": "ChIJ2",
                "name": "Restaurant 2",
                "cuisine_type": "bún",
                "rating": 4.0,
                "selected_at": datetime(2024, 1, 1)
            }
        ]

        class AsyncIteratorMock:
            def __init__(self, items):
                self.items = items
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.items):
                    raise StopAsyncIteration
                item = self.items[self.index]
                self.index += 1
                return item

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = lambda self: AsyncIteratorMock(mock_docs).__aiter__()

        mock_db.selections.find = MagicMock(return_value=mock_cursor)

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            selections = await selection_service.get_user_selections("u01", limit=10)

            assert len(selections) == 2
            assert selections[0].name == "Restaurant 1"  # Most recent first

# ============================================================
# TEST: Edge Cases
# ============================================================

class TestEdgeCases:
    """Test edge cases"""

    @pytest.mark.asyncio
    async def test_very_long_name(self, selection_service, mock_db):
        """Very long restaurant name should be saved"""
        long_name = "A" * 500

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()

            result = await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name=long_name
            )

            assert result.success
            assert result.selection.name == long_name

    @pytest.mark.asyncio
    async def test_special_characters_in_name(self, selection_service, mock_db):
        """Special characters in name should be handled"""
        special_name = "Quán 'Phở' & Bún - Ngon! (Test)"

        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()

            result = await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name=special_name
            )

            assert result.success
            assert result.selection.name == special_name

    @pytest.mark.asyncio
    async def test_unicode_cuisine_type(self, selection_service, mock_db):
        """Vietnamese cuisine names should be saved correctly"""
        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()

            result = await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name="Quán Ăn",
                cuisine_type="bún bò huế"
            )

            assert result.success
            assert result.selection.cuisine_type == "bún bò huế"

    @pytest.mark.asyncio
    async def test_zero_rating(self, selection_service, mock_db):
        """Rating of 0.0 should be accepted"""
        with patch("app.services.selection_service.get_db", return_value=mock_db):
            mock_db.find_one = AsyncMock(return_value=None)
            mock_db.insert_one = AsyncMock()

            result = await selection_service.save_selection(
                user_id="u01",
                place_id="ChIJxxx",
                name="New Restaurant",
                rating=0.0
            )

            assert result.success
            assert result.selection.rating == 0.0
```

### File: `tests/test_save_user_selection_tool.py`

```python
# tests/test_save_user_selection_tool.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.tools.memory_tool import (
    SaveUserSelectionTool,
    SaveUserSelectionInput
)
from app.services.selection_service import SelectionResponse
from app.db.models import Selection
from datetime import datetime

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_selection_service():
    """Mock SelectionService"""
    service = MagicMock()
    return service

@pytest.fixture
def save_tool(mock_selection_service):
    tool = SaveUserSelectionTool()
    tool.selection_service = mock_selection_service
    return tool

@pytest.fixture
def sample_response():
    """Sample successful response"""
    return SelectionResponse(
        success=True,
        message="Selection saved successfully",
        selection=Selection(
            user_id="u01",
            place_id="ChIJxxx",
            name="Phở Thìn",
            cuisine_type="phở",
            rating=4.5,
            selected_at=datetime.utcnow()
        ),
        preference_updated=True
    )

# ============================================================
# TEST: Tool Interface
# ============================================================

class TestSaveUserSelectionTool:

    @pytest.mark.asyncio
    async def test_tool_returns_success_format(self, save_tool, mock_selection_service, sample_response):
        """Tool should return dict with success status"""
        mock_selection_service.save_selection = AsyncMock(return_value=sample_response)

        result = await save_tool._arun(
            user_id="u01",
            place_id="ChIJxxx",
            name="Phở Thìn",
            cuisine_type="phở",
            rating=4.5
        )

        assert "success" in result
        assert result["success"] is True
        assert "message" in result
        assert "preference_updated" in result

    @pytest.mark.asyncio
    async def test_tool_passes_all_params(self, save_tool, mock_selection_service, sample_response):
        """Tool should pass all parameters to service"""
        mock_selection_service.save_selection = AsyncMock(return_value=sample_response)

        await save_tool._arun(
            user_id="u01",
            place_id="ChIJxxx",
            name="Phở Thìn",
            cuisine_type="phở",
            rating=4.5
        )

        mock_selection_service.save_selection.assert_called_once_with(
            user_id="u01",
            place_id="ChIJxxx",
            name="Phở Thìn",
            cuisine_type="phở",
            rating=4.5
        )

    @pytest.mark.asyncio
    async def test_tool_works_without_optional_params(self, save_tool, mock_selection_service, sample_response):
        """Tool should work when optional params are None"""
        mock_selection_service.save_selection = AsyncMock(return_value=sample_response)

        result = await save_tool._arun(
            user_id="u01",
            place_id="ChIJxxx",
            name="Quán Lạ"
        )

        assert result["success"]
        mock_selection_service.save_selection.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_with_default_rating(self, save_tool, mock_selection_service, sample_response):
        """Rating should default to 0.0"""
        mock_selection_service.save_selection = AsyncMock(return_value=sample_response)

        await save_tool._arun(
            user_id="u01",
            place_id="ChIJxxx",
            name="New Place"
        )

        call_kwargs = mock_selection_service.save_selection.call_args.kwargs
        assert call_kwargs["rating"] == 0.0

# ============================================================
# TEST: Input Validation
# ============================================================

class TestInputValidation:

    def test_input_schema_requires_user_id(self):
        """user_id should be required"""
        schema = SaveUserSelectionInput.model_json_schema()
        required = schema.get("required", [])
        assert "user_id" in required

    def test_input_schema_requires_place_id(self):
        """place_id should be required"""
        schema = SaveUserSelectionInput.model_json_schema()
        required = schema.get("required", [])
        assert "place_id" in required

    def test_input_schema_requires_name(self):
        """name should be required"""
        schema = SaveUserSelectionInput.model_json_schema()
        required = schema.get("required", [])
        assert "name" in required

    def test_input_schema_rating_has_default(self):
        """rating should have default value"""
        schema = SaveUserSelectionInput.model_json_schema()
        properties = schema.get("properties", {})
        assert "rating" in properties
        assert properties["rating"].get("default") == 0.0

    def test_input_schema_rating_range(self):
        """rating should have 0.0-5.0 range"""
        schema = SaveUserSelectionInput.model_json_schema()
        properties = schema.get("properties", {})
        assert "rating" in properties
        assert properties["rating"].get("minimum") == 0.0
        assert properties["rating"].get("maximum") == 5.0

    def test_valid_input_parsing(self):
        """Valid input should parse correctly"""
        input_data = SaveUserSelectionInput(
            user_id="u01",
            place_id="ChIJxxx",
            name="Phở Thìn",
            cuisine_type="phở",
            rating=4.5
        )

        assert input_data.user_id == "u01"
        assert input_data.place_id == "ChIJxxx"
        assert input_data.name == "Phở Thìn"
        assert input_data.cuisine_type == "phở"
        assert input_data.rating == 4.5

    def test_input_without_optional_fields(self):
        """Input without optional fields should work"""
        input_data = SaveUserSelectionInput(
            user_id="u01",
            place_id="ChIJxxx",
            name="Quán Mới"
        )

        assert input_data.cuisine_type is None
        assert input_data.rating == 0.0

# ============================================================
# TEST: Error Handling
# ============================================================

class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_tool_handles_service_error(self, save_tool, mock_selection_service):
        """Tool should handle service exceptions"""
        mock_selection_service.save_selection = AsyncMock(
            side_effect=ValueError("user_id is required")
        )

        with pytest.raises(ValueError):
            await save_tool._arun(
                user_id="",
                place_id="ChIJxxx",
                name="Test"
            )
```

---

## 6. Code Implementation

### Final File Structure

```
app/
├── services/
│   ├── __init__.py
│   ├── preference_service.py    # User preference management
│   └── selection_service.py     # Core selection logic
└── tools/
    ├── __init__.py
    └── memory_tool.py           # LangChain tool wrapper

app/db/
├── connection.py                # MongoDB connection
└── models.py                    # Pydantic models

tests/
├── conftest.py
├── test_selection_service.py    # Service tests
└── test_save_user_selection_tool.py  # Tool tests
```

### Run Tests

```bash
# Run all tests
pytest tests/test_selection_service.py tests/test_save_user_selection_tool.py -v

# Run with coverage
pytest tests/ --cov=app.services.selection_service --cov=app.tools.memory_tool

# Run specific test class
pytest tests/test_selection_service.py::TestValidation -v

# Run with asyncio
pytest tests/ -v --asyncio-mode=auto
```

---

## Checklist

- [ ] Tạo `app/db/models.py` - Selection, SelectionResponse models
- [ ] Tạo `app/db/connection.py` - MongoDB connection với indexes
- [ ] Tạo `app/services/preference_service.py` - Preference management
- [ ] Tạo `app/services/selection_service.py` - Core logic
- [ ] Tạo `app/tools/memory_tool.py` - LangChain tool wrapper
- [ ] Tạo `tests/test_selection_service.py` - 25+ test cases
- [ ] Tạo `tests/test_save_user_selection_tool.py` - Tool tests
- [ ] Chạy tests → all green ✓
- [ ] Update `app/tools/registry.py` để register tool
