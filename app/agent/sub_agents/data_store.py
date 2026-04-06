"""JSON-based data store for Phase 1 (no database).

Replace this module with MongoDB connection in Phase 2.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SELECTION_FILE = DATA_DIR / "selection_store.json"
USER_FILE = DATA_DIR / "user_preferences.json"

# Thread-safe lock for file I/O
_store_lock = Lock()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {} if "selection" in str(path) else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


# ── Selection operations ────────────────────────────────────────────────────────

def insert_selection(selection: dict[str, Any]) -> str:
    with _store_lock:
        store = _read_json(SELECTION_FILE)
        store.setdefault("selections", [])
        store["selections"].append(selection)
        _write_json(SELECTION_FILE, store)
        return selection.get("place_id", "")


def update_selection(user_id: str, place_id: str, updates: dict[str, Any]) -> bool:
    with _store_lock:
        store = _read_json(SELECTION_FILE)
        selections = store.get("selections", [])
        for i, sel in enumerate(selections):
            if sel.get("user_id") == user_id and sel.get("place_id") == place_id:
                selections[i].update(updates)
                store["selections"] = selections
                _write_json(SELECTION_FILE, store)
                return True
        return False


def find_selection(user_id: str, place_id: str) -> dict[str, Any] | None:
    store = _read_json(SELECTION_FILE)
    for sel in store.get("selections", []):
        if sel.get("user_id") == user_id and sel.get("place_id") == place_id:
            return sel
    return None


def list_selections(user_id: str, limit: int = 20, skip: int = 0) -> list[dict[str, Any]]:
    store = _read_json(SELECTION_FILE)
    user_sels = [
        s for s in store.get("selections", [])
        if s.get("user_id") == user_id
    ]
    user_sels.sort(key=lambda s: s.get("selected_at", ""), reverse=True)
    return user_sels[skip : skip + limit]


def count_selections(user_id: str) -> int:
    store = _read_json(SELECTION_FILE)
    return sum(1 for s in store.get("selections", []) if s.get("user_id") == user_id)


# ── User preference operations ──────────────────────────────────────────────────

def get_user_preference(user_id: str) -> dict[str, Any]:
    store = _read_json(USER_FILE)
    return store.get(user_id, {
        "user_id": user_id,
        "favorite_cuisines": [],
        "avoid_cuisines": [],
        "price_range": "mid",
        "preferred_ambiance": None,
    })


def upsert_user_preference(user_id: str, preference: dict[str, Any]) -> None:
    with _store_lock:
        store = _read_json(USER_FILE)
        store[user_id] = {**store.get(user_id, {}), **preference, "user_id": user_id}
        _write_json(USER_FILE, store)


def add_favorite_cuisine(user_id: str, cuisine: str) -> None:
    with _store_lock:
        store = _read_json(USER_FILE)
        if user_id not in store:
            store[user_id] = {
                "user_id": user_id,
                "favorite_cuisines": [],
                "avoid_cuisines": [],
                "price_range": "mid",
                "preferred_ambiance": None,
            }
        favs = store[user_id].setdefault("favorite_cuisines", [])
        if cuisine not in favs:
            favs.append(cuisine)
        _write_json(USER_FILE, store)


def remove_favorite_cuisine(user_id: str, cuisine: str) -> None:
    with _store_lock:
        store = _read_json(USER_FILE)
        if user_id in store:
            favs = store[user_id].get("favorite_cuisines", [])
            if cuisine in favs:
                favs.remove(cuisine)
            _write_json(USER_FILE, store)
