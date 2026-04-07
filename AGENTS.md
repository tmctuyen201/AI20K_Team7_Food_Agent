# AGENTS.md

This file provides comprehensive guidance for coding agents working on the Foodie Agent project. It contains build/lint/test commands, code style guidelines, and conventions to ensure consistency across the codebase.

## Project Overview

Foodie Agent is a ReAct-based chatbot that helps users find restaurants using Google Places API. It consists of:
- **Backend**: FastAPI (Python) with LLM-powered agent loop
- **Frontend**: React + TypeScript with Vite
- **Architecture**: ReAct agent using LangGraph, structured logging, MongoDB/JSON storage

## Build/Lint/Test Commands

### Python Backend

#### Environment Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Development Server
```bash
# Run FastAPI server with auto-reload
uvicorn app.server:app --reload --port 8000

# Alternative entry point
uvicorn app.main:app --reload --port 8000

# Run CLI version
python app/main.py
```

#### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_location_tool.py

# Run single test function
pytest tests/test_location_tool.py::test_get_user_location_tool_schema -v

# Run tests with coverage
pytest --cov=app --cov-report=html

# Run async tests
pytest -k "async" --asyncio-mode=auto
```

#### Code Quality
```bash
# Format code with Black
black app/ tests/

# Lint with Ruff (includes import sorting, unused imports, etc.)
ruff check app/ tests/

# Auto-fix Ruff issues
ruff check --fix app/ tests/

# Type checking (if mypy configured)
# Note: No mypy config found, but consider adding if needed
```

### Frontend (React + TypeScript)

#### Setup
```bash
cd frontend
npm install
```

#### Development
```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

#### Code Quality
```bash
# Lint with ESLint
npm run lint

# Type checking (automatic with build)
npm run build
```

### Full Project Commands

```bash
# Setup both backend and frontend
./scripts/setup.sh    # Linux/macOS
scripts\setup.bat     # Windows

# Run complete development environment
# Terminal 1 - Backend:
uvicorn app.server:app --reload --port 8000

# Terminal 2 - Frontend:
cd frontend && npm run dev
```

## Code Style Guidelines

### Python Backend

#### General Conventions
- **Python Version**: 3.10+
- **Line Length**: 88 characters (Black default)
- **Imports**: `from __future__ import annotations` at the top of all files
- **String Quotes**: Double quotes for docstrings and user-facing strings, single quotes for internal strings
- **Naming**:
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
  - Private members: `_leading_underscore`

#### Type Hints
```python
# Use comprehensive type hints
from typing import Any, Dict, List, Optional, Union
from __future__ import annotations

def process_data(data: Dict[str, Any]) -> Optional[List[str]]:
    # Implementation
    pass

class DataProcessor:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
```

#### Docstrings
Use Google-style docstrings:
```python
def get_user_location(state: AgentState) -> str:
    """Get the user's current location for restaurant search.

    Args:
        state: Current agent state containing user context.

    Returns:
        JSON string with location data or error message.

    Raises:
        ValueError: If location cannot be determined.
    """
    pass
```

#### Imports Organization
```python
# Standard library imports
import json
from typing import Any, Dict, List

# Third-party imports
import structlog
from pydantic import BaseModel

# Local imports (grouped by module)
from app.core.config import settings
from app.core.logging import get_logger
from app.services.location_service import LocationService
```

#### Error Handling
```python
# Use specific exceptions, log errors appropriately
try:
    result = await external_api_call()
except APIError as e:
    logger.error("API call failed", error=str(e), user_id=user_id)
    raise ValueError(f"Service unavailable: {e}") from e
except Exception as e:
    logger.exception("Unexpected error in location service")
    raise
```

#### Async/Await Patterns
```python
# Always use async/await for I/O operations
async def process_user_request(self, state: AgentState) -> AgentState:
    """Process a user request asynchronously."""
    location = await self.location_service.get_user_location(state)
    restaurants = await self.places_service.search_restaurants(location)
    return await self.score_restaurants(restaurants, state)
```

#### Logging
Use structured logging with domain prefixes:
```python
from app.core.logging import get_agent_logger, get_llm_logger

agent_logger = get_agent_logger()
llm_logger = get_llm_logger()

# Log with context
agent_logger.info(
    "agent_step_start",
    user_id=state.get("user_id"),
    session_id=state.get("session_id"),
    step="location_extraction"
)
```

#### Configuration
Never hardcode values - use the global settings singleton:
```python
from app.core.config import settings

# Correct
api_key = settings.google_places_api_key
model = f"{settings.llm_provider}/{settings.llm_model}"

# Incorrect - never do this
api_key = "hardcoded-key"
```

### Frontend (TypeScript + React)

#### TypeScript Configuration
- **Strict Mode**: Enabled (`"strict": true`)
- **JSX**: `"react-jsx"`
- **Module Resolution**: `"bundler"`
- **Unused Detection**: `"noUnusedLocals": true, "noUnusedParameters": true`

#### Component Structure
```typescript
// Use functional components with hooks
import React, { useState, useEffect } from 'react';

interface ChatMessageProps {
  message: string;
  timestamp: Date;
  isUser: boolean;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  timestamp,
  isUser
}) => {
  return (
    <div className={`message ${isUser ? 'user' : 'agent'}`}>
      <p>{message}</p>
      <span className="timestamp">
        {timestamp.toLocaleTimeString()}
      </span>
    </div>
  );
};
```

#### API Integration
```typescript
// Use async/await for API calls
export const chatAPI = {
  async sendMessage(message: string, sessionId: string): Promise<ChatResponse> {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  }
};
```

#### State Management
```typescript
// Use React hooks for local state
export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async (message: string) => {
    setIsLoading(true);
    try {
      const response = await chatAPI.sendMessage(message, sessionId);
      setMessages(prev => [...prev, response]);
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return { messages, isLoading, sendMessage };
};
```

## Tool Definitions and Schemas

### LiteLLM Tool Format
When adding new tools, ensure JSON schemas include `items` for arrays:
```python
# Correct - includes items for array types
{
    "type": "object",
    "properties": {
        "restaurants": {
            "type": "array",
            "items": {"type": "object"},  # Required!
            "description": "List of restaurants"
        }
    }
}

# Incorrect - missing items
{
    "type": "object",
    "properties": {
        "restaurants": {
            "type": "array",  # Causes BadRequestError
            "description": "List of restaurants"
        }
    }
}
```

### Tool Registration
Add new tools to `app/tools/definitions.py` and register handlers in `ReActAgent._route_tool()`.

## Testing Guidelines

### Unit Tests
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
async def mock_service():
    """Create mock service for testing."""
    service = AsyncMock()
    service.get_data.return_value = {"key": "value"}
    return service

@pytest.mark.asyncio
async def test_tool_integration(mock_service):
    """Test tool integration with mocked dependencies."""
    # Test implementation
    pass
```

### Integration Tests
```python
# Test full agent loops
async def test_agent_restaurant_search():
    """Test complete restaurant search flow."""
    state = AgentState(user_message="Find Italian restaurants in Hanoi")
    agent = ReActAgent(get_tool_definitions())

    result = await agent.run(state)

    assert result["is_done"] is True
    assert "restaurants" in result.get("final_response", "")
```

## File Organization

### Backend Structure
```
app/
├── api/           # FastAPI route handlers
├── agent/         # ReAct agent logic, LangGraph nodes
├── core/          # Config, logging, auth, guardrails
├── db/            # Database models, connections, queries
├── services/      # External API clients (Google, LLM)
└── tools/         # Tool definitions, registry, implementations
```

### Naming Conventions
- **Files**: `snake_case.py`
- **Directories**: `snake_case/`
- **Test Files**: `test_*.py`
- **API Routes**: RESTful with plural nouns (`/api/chat`, `/api/sessions`)

## Security Best Practices

- Never log API keys, tokens, or sensitive data
- Use environment variables for all secrets
- Validate all user inputs
- Implement rate limiting (configured via `settings.rate_limit_per_minute`)
- Use HTTPS in production
- Sanitize database queries to prevent injection

## Performance Considerations

- Use async/await for all I/O operations
- Implement caching for expensive operations (geocoding, API calls)
- Stream large responses when possible
- Monitor memory usage in long-running processes
- Use connection pooling for database/external API calls

## Common Patterns

### Agent State Management
```python
@dataclass
class AgentState:
    """TypedDict for agent state with proper typing."""
    user_id: str
    session_id: str
    user_message: str
    conversation_history: List[Dict[str, Any]]
    is_done: bool = False
    final_response: Optional[str] = None
```

### Service Layer Pattern
```python
class LocationService:
    """Service for handling user location operations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = httpx.AsyncClient()

    async def get_user_location(self, state: AgentState) -> LocationResult:
        """Get user location with fallback strategies."""
        # Implementation with proper error handling
        pass

    async def close(self):
        """Clean up resources."""
        await self.client.aclose()
```

This guide should be updated as the project evolves. When adding new tools, services, or significant architectural changes, update this document accordingly.</content>
<parameter name="filePath">D:\project\vinai\Day03-AI-Chatbot-labs\AGENTS.md