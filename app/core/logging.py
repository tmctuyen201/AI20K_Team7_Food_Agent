"""Structured logging system using structlog.

Logs are written to both stdout (for terminal) and log files.
All agent reasoning, tool calls, and LLM interactions are tracked.

A dedicated per-session JSONL logger (`get_agent_step_logger`) writes structured
step-by-step agent traces to `logs/agent_{session_id}.jsonl`.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

import structlog

from app.core.config import settings

# ── Log directory ────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ── Shared processor chain ──────────────────────────────────────────────────────

def add_timestamp(logger, method_name: str, event_dict: dict) -> dict:
    event_dict["timestamp"] = datetime.utcnow().isoformat(timespec="milliseconds")
    return event_dict


def add_log_level(logger, method_name: str, event_dict: dict) -> dict:
    event_dict["level"] = method_name.upper()
    return event_dict


# ── Configure standard library logging ─────────────────────────────────────────

logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
)

# ── Console / development structlog configuration ─────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        ),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance (colored console output in dev).

    Usage:
        logger = get_logger(__name__)
        logger.info("event_name", key="value")
    """
    return structlog.get_logger(name)


# ── Convenience loggers for specific domains ────────────────────────────────────

def get_agent_logger() -> structlog.stdlib.BoundLogger:
    return get_logger("foodie.agent")


def get_tool_logger() -> structlog.stdlib.BoundLogger:
    return get_logger("foodie.tools")


def get_llm_logger() -> structlog.stdlib.BoundLogger:
    return get_logger("foodie.llm")


# ── Re-export shared logger for convenience ────────────────────────────────────

logger = get_logger("foodie")


# ── Per-session agent-step JSONL logger ────────────────────────────────────────
#
# These loggers write structured JSON lines to logs/agent_{session_id}.jsonl.
# Each event follows the schema documented in the plan:
#   - agent.step   {step, phase, model, version, user_id, session_id, message}
#   - tool.call    {step, tool, args, user_id, session_id}
#   - tool.result  {step, tool, places_count|error, user_id, session_id}
#   - llm.response {version, model, tokens, user_id, session_id}
#
# The renderer writes one JSON line per log call so the file can be consumed
# with:  jq -s 'map(fromjson)' logs/agent_*.jsonl
# ─────────────────────────────────────────────────────────────────────────────

_agent_step_lock = threading.Lock()
_agent_step_loggers: dict[str, structlog.BoundLogger] = {}


def _agent_step_json_renderer(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> str:
    """Write a single event dict as one JSON line (no extra formatting).
    json.dumps returns one line; we strip the trailing newline that structlog
    normally adds after each processor return value.
    """
    return json.dumps(event_dict, ensure_ascii=False, default=str)


def _build_agent_step_logger(session_id: str) -> structlog.BoundLogger:
    """Create a structlog logger that writes JSONL to logs/agent_{session_id}.jsonl."""
    log_file = LOG_DIR / f"agent_{session_id}.jsonl"

    # Dedicated stdlib logger for this session's JSONL file
    stdlib_logger = logging.getLogger(f"foodie.agent_step.{session_id}")
    stdlib_logger.setLevel(logging.DEBUG)
    stdlib_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.DEBUG)
    stdlib_logger.addHandler(file_handler)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _agent_step_json_renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(stdlib_logger),
        cache_logger_on_first_use=False,
    )
    return structlog.get_logger(f"foodie.agent_step.{session_id}")


def get_agent_step_logger(session_id: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger that writes structured JSON lines to
    ``logs/agent_{session_id}.jsonl``.

    The returned logger produces events conforming to the agent-step schema:
      - ``agent.step``   — agent reasoning / scoring phase
      - ``tool.call``    — tool invocation started
      - ``tool.result``  — tool result received
      - ``llm.response`` — LLM response complete

    Each call with the same ``session_id`` returns the same logger instance
    (thread-safe, lazily created).

    Example JSONL output::

        {"timestamp":"...","level":"INFO","event":"agent.step",
         "step":1,"phase":"think","model":"gpt-4o-mini","version":"v2",
         "user_id":"u01","session_id":"sess_abc","message":"Thinking..."}
        {"timestamp":"...","level":"INFO","event":"tool.call",
         "step":2,"tool":"search_google_places",
         "args":{"keyword":"Italian","location":[10.76,106.7]},
         "user_id":"u01","session_id":"sess_abc"}
        {"timestamp":"...","level":"INFO","event":"tool.result",
         "step":2,"tool":"search_google_places","places_count":5,
         "user_id":"u01","session_id":"sess_abc"}
        {"timestamp":"...","level":"INFO","event":"llm.response",
         "version":"v2","model":"gpt-4o-mini","tokens":342,
         "user_id":"u01","session_id":"sess_abc"}
    """
    with _agent_step_lock:
        if session_id in _agent_step_loggers:
            return _agent_step_loggers[session_id]
        bound = _build_agent_step_logger(session_id)
        _agent_step_loggers[session_id] = bound
        return bound


# ── Convenience helpers for structured agent events ───────────────────────────
# Callers pass the logger returned by get_agent_step_logger().
# All helpers accept a structlog.BoundLogger as first positional arg.


def log_agent_step(
    logger: structlog.stdlib.BoundLogger,
    *,
    step: int,
    phase: str,  # "think" | "tool" | "score" | "done"
    model: str,
    version: str,
    user_id: str,
    session_id: str,
    message: str,
) -> None:
    """Emit an ``agent.step`` event."""
    logger.info(
        "agent.step",
        step=step,
        phase=phase,
        model=model,
        version=version,
        user_id=user_id,
        session_id=session_id,
        message=message,
    )


def log_tool_call(
    logger: structlog.stdlib.BoundLogger,
    *,
    step: int,
    tool: str,
    args: dict,
    user_id: str,
    session_id: str,
) -> None:
    """Emit a ``tool.call`` event."""
    logger.info(
        "tool.call",
        step=step,
        tool=tool,
        args=args,
        user_id=user_id,
        session_id=session_id,
    )


def log_tool_result(
    logger: structlog.stdlib.BoundLogger,
    *,
    step: int,
    tool: str,
    places_count: int | None = None,
    error: str | None = None,
    user_id: str,
    session_id: str,
) -> None:
    """Emit a ``tool.result`` event.

    Pass either ``places_count`` (int) for success or ``error`` (str) for failure,
    but not both.
    """
    payload = {
        "step": step,
        "tool": tool,
        "user_id": user_id,
        "session_id": session_id,
    }
    if error is not None:
        payload["error"] = error
    else:
        payload["places_count"] = places_count

    if error:
        logger.error("tool.result", **payload)
    else:
        logger.info("tool.result", **payload)


def log_llm_response(
    logger: structlog.stdlib.BoundLogger,
    *,
    version: str,
    model: str,
    tokens: int,
    user_id: str,
    session_id: str,
) -> None:
    """Emit an ``llm.response`` event."""
    logger.info(
        "llm.response",
        version=version,
        model=model,
        tokens=tokens,
        user_id=user_id,
        session_id=session_id,
    )


# ── Session / file logging ─────────────────────────────────────────────────────

class SessionLogHandler:
    """Optional file handler that writes per-session logs.

    Use this in production / review mode to dump full agent traces.
    """

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.log_file = LOG_DIR / f"session_{self.session_id}.log"
        self._file_handler: logging.FileHandler | None = None

    def attach(self) -> None:
        if self._file_handler is not None:
            return
        self._file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        self._file_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(self._file_handler)

    def detach(self) -> None:
        if self._file_handler is not None:
            logging.getLogger().removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None

    @property
    def log_path(self) -> Path:
        return self.log_file