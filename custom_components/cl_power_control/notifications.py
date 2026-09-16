"""Pre-intervention notifications for CL Power Control."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import (
    CONF_PREALERT_ENABLED,
    DEFAULT_PREALERT_ENABLED,
    DOMAIN,
    EVENT_PREALERT,
)


class CLPrealertManager:
    """Notify the user before Power Control starts shedding loads."""

    def __init__(self, hass: HomeAssistant, entry, coordinator) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._unsub = None
        self._warning_sent = False
        self._immediate_sent = False

    async def async_setup(self) -> None:
        self._unsub = self.coordinator.async_add_listener(self._handle_update)
        self._handle_update()

    def unload(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    def _enabled(self) -> bool:
        return bool(self.entry.options.get(CONF_PREALERT_ENABLED, DEFAULT_PREALERT_ENABLED))

    def _handle_update(self) -> None:
        data = self.coordinator.data or {}
        current = data.get("current_power")
        warning = data.get("warning_w")
        limit = data.get("limit_w")
        if current is None or warning is None or limit is None:
            return

        current = float(current)
        warning = float(warning)
        limit = float(limit)

        if current < warning:
            self._warning_sent = False
            self._immediate_sent = False
            self.hass.async_create_task(self._dismiss())
            return

        if not self._enabled():
            return

        if current >= limit:
            if not self._immediate_sent:
                self._immediate_sent = True
                delay = int(self.coordinator.conf("delay_immediate_sec", 5))
                self.hass.async_create_task(
                    self._notify("immediata", current, limit, delay)
                )
            return

        if current >= warning and not self._warning_sent:
            self._warning_sent = True
            delay = int(self.coordinator.conf("delay_warning_sec", 120))
            self.hass.async_create_task(
                self._notify("ritardata", current, warning, delay)
            )

    async def _notify(self, kind: str, current: float, threshold: float, delay: int) -> None:
        if kind == "immediata":
            title = "CL Power Control - intervento imminente"
            message = (
                f"Assorbimento {current:.0f} W oltre la soglia immediata di {threshold:.0f} W. "
                f"Se il consumo non scende, il sistema potrà distaccare un carico tra circa {delay} secondi. "
                "Riduci ora i consumi se vuoi evitare l'intervento automatico."
            )
        else:
            minutes = max(1, round(delay / 60))
            title = "CL Power Control - consumo elevato"
            message = (
                f"Assorbimento {current:.0f} W oltre la soglia ritardata di {threshold:.0f} W. "
                f"Se resta sopra soglia, Power Control potrà intervenire tra circa {minutes} minuti. "
                "Riduci i consumi per evitare il distacco automatico."
            )

        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": f"{DOMAIN}_{self.entry.entry_id}_prealert",
            },
            blocking=False,
        )
        self.hass.bus.async_fire(
            EVENT_PREALERT,
            {
                "entry_id": self.entry.entry_id,
                "type": kind,
                "current_power_w": round(current, 1),
                "threshold_w": round(threshold, 1),
                "delay_sec": delay,
                "title": title,
                "message": message,
            },
        )

    async def _dismiss(self) -> None:
        if not self.hass.services.has_service("persistent_notification", "dismiss"):
            return
        await self.hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": f"{DOMAIN}_{self.entry.entry_id}_prealert"},
            blocking=False,
        )
