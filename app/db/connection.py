"""JSON file-based storage — no MongoDB required."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger("foodie.db.connection")

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)

_USERS_FILE = _DATA_DIR / "users.json"
_SESSIONS_FILE = _DATA_DIR / "sessions.json"
_SELECTIONS_FILE = _DATA_DIR / "selections.json"


class _JSONStore:
    """Thread-safe JSON file storage."""

    def __init__(self, filepath: Path) -> None:
        self._filepath = filepath
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self._filepath.exists():
            self._filepath.write_text("{}", encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        with self._lock:
            try:
                return json.loads(self._filepath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, FileNotFoundError):
                return {}

    def _write(self, data: dict[str, Any]) -> None:
        with self._lock:
            self._filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self._read().get(key, default)

    def set(self, key: str, value: Any) -> None:
        data = self._read()
        data[key] = value
        self._write(data)

    def delete(self, key: str) -> None:
        data = self._read()
        data.pop(key, None)
        self._write(data)

    def items(self) -> list[tuple[str, Any]]:
        return list(self._read().items())

    def values(self) -> list[Any]:
        return list(self._read().values())

    def keys(self) -> list[str]:
        return list(self._read().keys())

    def __contains__(self, key: str) -> bool:
        return key in self._read()

    def __len__(self) -> int:
        return len(self._read())


# Per-collection stores
users_store = _JSONStore(_USERS_FILE)
sessions_store = _JSONStore(_SESSIONS_FILE)
selections_store = _JSONStore(_SELECTIONS_FILE)


async def connect_db() -> None:
    """Initialise JSON stores (no-op, files are created on demand)."""
    logger.info("json_store_initialized", data_dir=str(_DATA_DIR))


async def close_db() -> None:
    """No-op for JSON storage."""
    logger.info("json_store_closed")


def get_db() -> dict[str, _JSONStore]:
    """Return all stores for compatibility."""
    return {
        "users": users_store,
        "sessions": sessions_store,
        "selections": selections_store,
    }
