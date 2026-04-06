"""Structured logging system using structlog.

Logs are written to both stdout (for terminal) and log files.
All agent reasoning, tool calls, and LLM interactions are tracked.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import structlog

from app.core.config import settings

# ── Log directory ──────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ── Logging processor chain ────────────────────────────────────────────────────

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

# ── Configure structlog ────────────────────────────────────────────────────────

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
    """Get a structured logger instance.

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
        # Root logger captures everything
        logging.getLogger().addHandler(self._file_handler)

    def detach(self) -> None:
        if self._file_handler is not None:
            logging.getLogger().removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None

    @property
    def log_path(self) -> Path:
        return self.log_file
