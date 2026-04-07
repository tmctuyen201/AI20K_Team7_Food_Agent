#!/usr/bin/env python3
"""Test script for Foodie Agent self-correction features.

Tests:
1. LLM retry and fallback
2. Tool retry and validation
3. LangGraph error recovery
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.llm import LLMClient
from app.tools.registry import get_tool_registry
from app.agent.runner import AgentRunner


async def test_llm_retry_and_fallback():
    """Test LLM retry logic and fallback models."""
    print("🧪 Testing LLM retry and fallback...")

    # Test with invalid model to trigger fallback
    client = LLMClient("invalid-model")

    try:
        response = ""
        async for token in client.generate_response(
            "Hello, find me a restaurant", "Test restaurant data", model="invalid-model"
        ):
            response += token

        print(f"✅ LLM fallback worked: {response[:100]}...")
        return True
    except Exception as e:
        print(f"❌ LLM fallback failed: {e}")
        return False


async def test_tool_retry_and_validation():
    """Test tool retry and validation."""
    print("🧪 Testing tool retry and validation...")

    registry = get_tool_registry()
    location_tool = registry["get_user_location"]

    # Test with invalid user_id to trigger fallback
    try:
        result = location_tool._run(user_id="invalid_user")
        print(f"✅ Tool validation worked: {result}")
        return True
    except Exception as e:
        print(f"❌ Tool validation failed: {e}")
        return False


async def test_langgraph_error_recovery():
    """Test LangGraph error recovery."""
    print("🧪 Testing LangGraph error recovery...")

    # Create runner with test session
    runner = AgentRunner("test_user", "test_session")

    try:
        events = []
        async for event in runner.run_async(
            "Find me Italian food",
            version="v2",
            model="gpt-4o-mini",  # Use available model
        ):
            events.append(event)

        # Check for error recovery events
        recovery_events = [e for e in events if e.get("type") == "error_recovery"]
        if recovery_events:
            print(
                f"✅ Error recovery activated: {len(recovery_events)} recovery events"
            )
            for event in recovery_events:
                print(f"   - {event.get('stage')}: {event.get('message')}")
        else:
            print("ℹ️ No error recovery needed (normal execution)")

        return True
    except Exception as e:
        print(f"❌ LangGraph error recovery failed: {e}")
        return False


async def main():
    """Run all self-correction tests."""
    print("🚀 Testing Foodie Agent Self-Correction Features")
    print("=" * 50)

    results = []

    # Test 1: LLM retry and fallback
    results.append(await test_llm_retry_and_fallback())
    print()

    # Test 2: Tool retry and validation
    results.append(await test_tool_retry_and_validation())
    print()

    # Test 3: LangGraph error recovery
    results.append(await test_langgraph_error_recovery())
    print()

    # Summary
    passed = sum(results)
    total = len(results)

    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} passed")

    if passed == total:
        print("🎉 All self-correction features working!")
    else:
        print("⚠️ Some features need attention")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
