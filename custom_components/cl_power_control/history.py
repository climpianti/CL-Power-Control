"""Persistent intervention history for CL Power Control."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    CONF_LOADS,
    DOMAIN,
    EVENT_LOAD_RESTORED,
    EVENT_LOAD_SHED,
    LOAD_ID,
    LOAD_NAME,
    LOAD_PRIORITY,
)

_HISTORY_VERSION = 1
_HISTORY_LIMIT = 20


class CLIncidentHistory:
    """Group shed/restore actions into persistent intervention incidents."""

    def __init__(self, hass: HomeAssistant, entry, coordinator) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._store = Store(
            hass,
            _HISTORY_VERSION,
            f"{DOMAIN}.history.{entry.entry_id}",
        )
        self.events: list[dict[str, Any]] = []
        self._unsubs = []

    async def async_setup(self) -> None:
        """Load history and start listening to Power Control actions."""
        stored = await self._store.async_load()
        if isinstance(stored, dict) and isinstance(stored.get("events"), list):
            self.events = stored["events"][-_HISTORY_LIMIT:]

        # An intervention left open by a restart cannot safely be continued.
        if self.events and not self.events[-1].get("ended_at"):
            self.events[-1]["ended_at"] = self._now()
            self.events[-1]["close_reason"] = "Riavvio Home Assistant"
            await self._async_save()

        self._unsubs = [
            self.hass.bus.async_listen(EVENT_LOAD_SHED, self._async_on_shed),
            self.hass.bus.async_listen(EVENT_LOAD_RESTORED, self._async_on_restore),
        ]

    def unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @property
    def incident_count(self) -> int:
        return len(self.events)

    @property
    def latest(self) -> dict[str, Any] | None:
        return self.events[-1] if self.events else None

    @property
    def recent(self) -> list[dict[str, Any]]:
        """Return a compact recent history suitable for entity attributes."""
        compact: list[dict[str, Any]] = []
        for incident in reversed(self.events[-5:]):
            compact.append({
                "id": incident.get("id"),
                "started_at": incident.get("started_at"),
                "ended_at": incident.get("ended_at"),
                "reason": incident.get("reason"),
                "system_power_w": incident.get("system_power_w"),
                "threshold_w": incident.get("threshold_w"),
                "loads": incident.get("snapshot", []),
                "actions": incident.get("actions", []),
            })
        return compact

    def _now(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _belongs_to_entry(self, load_id: str) -> bool:
        return any(
            item.get(LOAD_ID) == load_id
            for item in self.entry.data.get(CONF_LOADS, [])
        )

    def _snapshot(self) -> list[dict[str, Any]]:
        """Take a picture of configured loads and their power at intervention time."""
        data = self.coordinator.data or {}
        result: list[dict[str, Any]] = []
        for load in data.get("loads", []):
            result.append({
                "load_id": load.get(LOAD_ID),
                "name": load.get(LOAD_NAME, "Carico"),
                "priority": load.get(LOAD_PRIORITY),
                "power_w": round(float(load.get("current_power", 0) or 0), 1),
                "state": load.get("switch_state"),
                "suspended": bool(load.get("suspended")),
            })
        return sorted(
            result,
            key=lambda item: float(item.get("power_w") or 0),
            reverse=True,
        )

    def _active(self) -> dict[str, Any] | None:
        latest = self.latest
        if latest and not latest.get("ended_at"):
            return latest
        return None

    async def _async_on_shed(self, event: Event) -> None:
        payload = event.data
        load_id = str(payload.get("load_id", ""))
        if not load_id or not self._belongs_to_entry(load_id):
            return

        incident = self._active()
        if incident is None:
            data = self.coordinator.data or {}
            reason = str(payload.get("reason", "sconosciuto"))
            threshold = (
                data.get("limit_w")
                if reason == "immediato"
                else data.get("warning_w")
            )
            started = self._now()
            incident = {
                "id": started,
                "started_at": started,
                "ended_at": None,
                "close_reason": None,
                "reason": reason,
                "system_power_w": round(float(payload.get("system_power_w", 0) or 0), 1),
                "threshold_w": round(float(threshold or 0), 1),
                "snapshot": self._snapshot(),
                "actions": [],
            }
            self.events.append(incident)
            self.events = self.events[-_HISTORY_LIMIT:]

        incident["actions"].append({
            "at": self._now(),
            "type": "distacco",
            "load_id": load_id,
            "name": payload.get("load_name", "Carico"),
            "priority": payload.get("priority"),
            "power_w": round(float(payload.get("power_w", 0) or 0), 1),
            "system_power_w": round(float(payload.get("system_power_w", 0) or 0), 1),
        })
        await self._async_save()

    async def _async_on_restore(self, event: Event) -> None:
        payload = event.data
        load_id = str(payload.get("load_id", ""))
        if not load_id or not self._belongs_to_entry(load_id):
            return

        incident = self._active()
        if incident is None:
            return

        incident["actions"].append({
            "at": self._now(),
            "type": "riattivazione",
            "load_id": load_id,
            "name": payload.get("load_name", "Carico"),
            "priority": payload.get("priority"),
            "power_w": round(float(payload.get("restored_power_w", 0) or 0), 1),
            "system_power_w": round(float(payload.get("system_power_w", 0) or 0), 1),
        })

        # The coordinator removes the load from _suspended before firing the event.
        if not getattr(self.coordinator, "_suspended", {}):
            incident["ended_at"] = self._now()
            incident["close_reason"] = "Tutti i carichi riattivati"

        await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save({"events": self.events[-_HISTORY_LIMIT:]})
