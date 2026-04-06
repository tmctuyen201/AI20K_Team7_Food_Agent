# LangGraph agent package

from app.agent.runner import AgentRunner
from app.agent.state import AgentState

__all__ = ["AgentRunner", "create_agent_graph", "AgentState"]


def create_agent_graph(*args, **kwargs):
    """Lazily import and create the LangGraph agent graph."""
    from app.agent.graph import create_agent_graph as _create
    return _create(*args, **kwargs)
