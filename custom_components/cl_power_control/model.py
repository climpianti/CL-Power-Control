"""Data model helpers for CL Power Control."""
from __future__ import annotations

from uuid import uuid4

from .const import (
    LOAD_ID, LOAD_NAME, LOAD_SWITCH, LOAD_POWER_SENSOR, LOAD_PRIORITY,
    LOAD_ENABLED, LOAD_AUTO_RESTART, LOAD_NEVER_SHED, LOAD_MIN_ACTIVE_W,
    LOAD_ESTIMATED_W,
)


def new_load(data: dict) -> dict:
    """Normalize a new managed load."""
    return {
        LOAD_ID: uuid4().hex,
        LOAD_NAME: str(data.get(LOAD_NAME, "Carico")),
        LOAD_SWITCH: data.get(LOAD_SWITCH, "") or "",
        LOAD_POWER_SENSOR: data.get(LOAD_POWER_SENSOR, "") or "",
        LOAD_PRIORITY: int(data.get(LOAD_PRIORITY, 10)),
        LOAD_ENABLED: bool(data.get(LOAD_ENABLED, True)),
        LOAD_AUTO_RESTART: bool(data.get(LOAD_AUTO_RESTART, True)),
        LOAD_NEVER_SHED: bool(data.get(LOAD_NEVER_SHED, False)),
        LOAD_MIN_ACTIVE_W: float(data.get(LOAD_MIN_ACTIVE_W, 10)),
        LOAD_ESTIMATED_W: float(data.get(LOAD_ESTIMATED_W, 0)),
    }


def normalize_priorities(loads: list[dict]) -> list[dict]:
    """Return loads sorted and numbered 1..N without duplicate priorities."""
    ordered = sorted(
        loads,
        key=lambda item: (int(item.get(LOAD_PRIORITY, 999)), item.get(LOAD_NAME, "")),
    )
    return [{**item, LOAD_PRIORITY: index + 1} for index, item in enumerate(ordered)]


def move_load_to_priority(loads: list[dict], load_id: str, priority: int) -> list[dict]:
    """Move one load to a requested priority and shift all others."""
    ordered = normalize_priorities(list(loads))
    selected = next((item for item in ordered if item.get(LOAD_ID) == load_id), None)
    if selected is None:
        return ordered
    remaining = [item for item in ordered if item.get(LOAD_ID) != load_id]
    new_index = max(0, min(int(priority) - 1, len(remaining)))
    remaining.insert(new_index, selected)
    return [{**item, LOAD_PRIORITY: index + 1} for index, item in enumerate(remaining)]


def sort_loads(loads: list[dict]) -> list[dict]:
    return normalize_priorities(loads)
