"""Load-management engine for CL Power Control."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import *
from .model import move_load_to_priority, normalize_priorities
from .security import verify_pin

_LOGGER = logging.getLogger(__name__)


class CLPowerControlCoordinator(DataUpdateCoordinator[dict]):
    """Monitor total power and shed/restore configured loads."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=2),
        )
        self.entry = entry
        self._suspended: dict[str, float] = {}
        self._shed_at: dict[str, datetime] = {}
        self._climate_restore_modes: dict[str, str] = {}
        self._over_limit_since: datetime | None = None
        self._over_warning_since: datetime | None = None
        self._under_restore_since: datetime | None = None
        self._last_shed: datetime | None = None
        self._last_restore: datetime | None = None
        self.last_event = ""
        sessions = hass.data.setdefault(DOMAIN, {}).setdefault("_installer_sessions", {})
        self._installer_sessions = sessions
        self._pending_installer_pin: str = ""
        self._installer_message: str = "Bloccato"

    @property
    def installer_unlocked(self) -> bool:
        """Return True while the installer session is valid."""
        until = self._installer_sessions.get(self.entry.entry_id)
        if until is None:
            return False
        if datetime.now() >= until:
            self._installer_sessions.pop(self.entry.entry_id, None)
            return False
        return True

    @property
    def installer_remaining_sec(self) -> int:
        until = self._installer_sessions.get(self.entry.entry_id)
        if until is None:
            return 0
        remaining = int((until - datetime.now()).total_seconds())
        if remaining <= 0:
            self._installer_sessions.pop(self.entry.entry_id, None)
            return 0
        return remaining

    def set_pending_installer_pin(self, pin: str) -> None:
        """Store a PIN only in memory until the unlock button is pressed."""
        self._pending_installer_pin = str(pin or "").strip()
        self._installer_message = "PIN inserito - premi Sblocca" if self._pending_installer_pin else "Bloccato"

    @property
    def installer_access_status(self) -> str:
        """Human-readable dashboard feedback for installer authentication."""
        if self.installer_unlocked:
            remaining = self.installer_remaining_sec
            minutes, seconds = divmod(max(0, remaining), 60)
            return f"Sbloccato - {minutes}m {seconds:02d}s"
        return self._installer_message

    async def async_unlock_pending_installer(self) -> bool:
        """Try to unlock using the transient PIN entered from the dashboard."""
        pin = self._pending_installer_pin
        if not pin:
            self._installer_message = "Inserisci il PIN"
            await self.async_request_refresh()
            return False
        try:
            return await self.async_unlock_installer(pin)
        finally:
            self._pending_installer_pin = ""

    async def async_unlock_installer(self, pin: str) -> bool:
        """Validate PIN and open a temporary installer session."""
        salt = self.entry.data.get(CONF_INSTALLER_PIN_SALT, "")
        digest = self.entry.data.get(CONF_INSTALLER_PIN_HASH, "")
        if not verify_pin(pin, salt, digest):
            self._installer_message = "PIN non valido"
            _LOGGER.warning("Invalid installer PIN for CL Power Control")
            await self.async_request_refresh()
            return False
        self._installer_sessions[self.entry.entry_id] = (
            datetime.now() + timedelta(minutes=INSTALLER_SESSION_MINUTES)
        )
        self._installer_message = "Sbloccato"
        _LOGGER.info("Installer mode unlocked for %d minutes", INSTALLER_SESSION_MINUTES)
        await self.async_request_refresh()
        return True

    def lock_installer(self) -> None:
        """Immediately close the installer session."""
        self._installer_sessions.pop(self.entry.entry_id, None)
        self._pending_installer_pin = ""
        self._installer_message = "Bloccato"

    async def async_update_load_field(self, load_id: str, field: str, value) -> None:
        """Update one load field from protected dashboard controls."""
        if not self.installer_unlocked:
            _LOGGER.warning("Installer-only load update rejected while locked")
            return
        allowed = {
            LOAD_SWITCH,
            LOAD_POWER_SENSOR,
            LOAD_ENABLED,
            LOAD_AUTO_RESTART,
            LOAD_NEVER_SHED,
            LOAD_MIN_ACTIVE_W,
            LOAD_ESTIMATED_W,
        }
        if field not in allowed:
            raise ValueError(f"Unsupported dashboard load field: {field}")
        loads = []
        for item in self.entry.data.get(CONF_LOADS, []):
            loads.append({**item, field: value} if item.get(LOAD_ID) == load_id else item)
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, CONF_LOADS: normalize_priorities(loads)}
        )
        await self.async_request_refresh()

    async def async_update_global_option(self, key: str, value) -> None:
        """Update an installer-only global option from dashboard controls."""
        if not self.installer_unlocked:
            _LOGGER.warning("Installer-only global update rejected while locked")
            return
        allowed = {
            CONF_LIMIT_W,
            CONF_WARNING_W,
            CONF_RESTORE_W,
            CONF_DELAY_IMMEDIATE_SEC,
            CONF_DELAY_WARNING_SEC,
            CONF_WAIT_BETWEEN_SHEDS_SEC,
            CONF_WAIT_BEFORE_RESTORE_SEC,
            CONF_WAIT_BETWEEN_RESTORES_SEC,
        }
        if key not in allowed:
            raise ValueError(f"Unsupported dashboard global option: {key}")
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, key: value}
        )
        await self.async_request_refresh()

    async def async_test_load(self, load_id: str, turn_on: bool) -> bool:
        """Manually test the configured command entity without changing suspension state."""
        if not self.installer_unlocked:
            _LOGGER.warning("Installer-only test rejected while locked")
            return False
        load = next(
            (x for x in self.entry.data.get(CONF_LOADS, []) if x.get(LOAD_ID) == load_id),
            None,
        )
        if not load:
            return False
        ok = await self._call_load(load, turn_on)
        if ok:
            action = "ON" if turn_on else "OFF"
            self.last_event = f"Test {action}: {load.get(LOAD_NAME, 'Carico')}"
            await self.async_request_refresh()
        return ok

    def conf(self, key: str, default=None):
        if key in self.entry.options:
            return self.entry.options[key]
        return self.entry.data.get(key, default)

    def _read_float(self, entity_id: str) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _entity_domain(self, entity_id: str) -> str:
        return entity_id.split(".", 1)[0] if entity_id and "." in entity_id else ""

    def _load_is_active(self, load: dict) -> bool:
        """Return whether a configured load is actually active."""
        entity_id = load.get(LOAD_SWITCH, "")
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in ("unknown", "unavailable", "", "off"):
            return False

        if self._entity_domain(entity_id) == "climate":
            hvac_action = str(state.attributes.get("hvac_action", "")).lower()
            if hvac_action in ("off", "idle"):
                return False
            return True

        return state.state == "on"

    def _load_power(self, load: dict) -> float:
        measured = self._read_float(load.get(LOAD_POWER_SENSOR, ""))
        if measured is not None:
            return measured
        if not self._load_is_active(load):
            return 0.0
        return float(load.get(LOAD_ESTIMATED_W, 0) or 0)

    def _switch_state(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.state if state else "unknown"

    async def _call_entity(self, entity_id: str, turn_on: bool) -> bool:
        if not entity_id or "." not in entity_id:
            return False
        domain = self._entity_domain(entity_id)
        service = "turn_on" if turn_on else "turn_off"
        if not self.hass.services.has_service(domain, service):
            _LOGGER.warning("No service %s.%s for %s", domain, service, entity_id)
            return False
        try:
            await self.hass.services.async_call(
                domain, service, {"entity_id": entity_id}, blocking=True
            )
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed %s.%s on %s: %s", domain, service, entity_id, err)
            return False

    async def _call_climate(self, load: dict, turn_on: bool) -> bool:
        """Switch a climate load without cutting mains power."""
        entity_id = load.get(LOAD_SWITCH, "")
        load_id = str(load.get(LOAD_ID, ""))
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return False

        hvac_modes = [str(mode) for mode in state.attributes.get("hvac_modes", [])]
        current_mode = str(state.state or "")

        if not turn_on:
            if current_mode not in ("", "off", "unknown", "unavailable"):
                self._climate_restore_modes[load_id] = current_mode

            if "off" in hvac_modes and self.hass.services.has_service("climate", "set_hvac_mode"):
                service = "set_hvac_mode"
                data = {"entity_id": entity_id, "hvac_mode": "off"}
            elif self.hass.services.has_service("climate", "turn_off"):
                service = "turn_off"
                data = {"entity_id": entity_id}
            elif self.hass.services.has_service("climate", "set_hvac_mode"):
                service = "set_hvac_mode"
                data = {"entity_id": entity_id, "hvac_mode": "off"}
            else:
                _LOGGER.warning("No supported climate OFF service for %s", entity_id)
                return False
        else:
            restore_mode = self._climate_restore_modes.get(load_id, "")
            if (
                restore_mode
                and restore_mode != "off"
                and (not hvac_modes or restore_mode in hvac_modes)
                and self.hass.services.has_service("climate", "set_hvac_mode")
            ):
                service = "set_hvac_mode"
                data = {"entity_id": entity_id, "hvac_mode": restore_mode}
            elif self.hass.services.has_service("climate", "turn_on"):
                service = "turn_on"
                data = {"entity_id": entity_id}
            else:
                preferred = ("auto", "heat_cool", "cool", "heat", "dry", "fan_only")
                fallback_mode = next(
                    (mode for mode in preferred if mode in hvac_modes),
                    next((mode for mode in hvac_modes if mode != "off"), ""),
                )
                if not fallback_mode or not self.hass.services.has_service("climate", "set_hvac_mode"):
                    _LOGGER.warning("No supported climate ON service for %s", entity_id)
                    return False
                service = "set_hvac_mode"
                data = {"entity_id": entity_id, "hvac_mode": fallback_mode}

        try:
            await self.hass.services.async_call("climate", service, data, blocking=True)
            if turn_on:
                self._climate_restore_modes.pop(load_id, None)
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed climate.%s on %s: %s", service, entity_id, err)
            return False

    async def _call_load(self, load: dict, turn_on: bool) -> bool:
        entity_id = load.get(LOAD_SWITCH, "")
        if self._entity_domain(entity_id) == "climate":
            return await self._call_climate(load, turn_on)
        return await self._call_entity(entity_id, turn_on)

    async def async_set_priority(self, load_id: str, priority: int) -> None:
        loads = move_load_to_priority(
            list(self.entry.data.get(CONF_LOADS, [])), load_id, priority
        )
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, CONF_LOADS: loads}
        )
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict:
        try:
            raw_loads = normalize_priorities(list(self.entry.data.get(CONF_LOADS, [])))
            global_power = self._read_float(self.conf(CONF_POWER_SENSOR, ""))
            virtual_total = sum(self._load_power(load) for load in raw_loads)
            current = global_power if global_power is not None else virtual_total

            limit_w = float(self.conf(CONF_LIMIT_W, DEFAULT_LIMIT_W))
            warning_w = float(self.conf(CONF_WARNING_W, DEFAULT_WARNING_W))
            restore_w = float(self.conf(CONF_RESTORE_W, DEFAULT_RESTORE_W))
            enabled = bool(self.conf(CONF_ENABLED, True))

            if enabled:
                await self._manage_power(current, raw_loads, limit_w, warning_w, restore_w)
            else:
                self._reset_timers()

            load_states = []
            for load in raw_loads:
                load_id = load[LOAD_ID]
                power = self._load_power(load)
                switch_state = self._switch_state(load.get(LOAD_SWITCH, ""))
                suspended = load_id in self._suspended
                if suspended and self._load_is_active(load) and power > float(load.get(LOAD_MIN_ACTIVE_W, 10)):
                    self._suspended.pop(load_id, None)
                    self._shed_at.pop(load_id, None)
                    suspended = False
                load_states.append({
                    **load,
                    "current_power": power,
                    "switch_state": switch_state,
                    "suspended": suspended,
                    "suspended_power": self._suspended.get(load_id, 0.0),
                })

            return {
                "current_power": round(current, 1),
                "source": "global" if global_power is not None else "virtual",
                "limit_w": limit_w,
                "warning_w": warning_w,
                "restore_w": restore_w,
                "headroom_w": round(limit_w - current, 1),
                "load_count": len(raw_loads),
                "suspended_count": len(self._suspended),
                "suspended_power": round(sum(self._suspended.values()), 1),
                "enabled": enabled,
                "last_event": self.last_event,
                "installer_unlocked": self.installer_unlocked,
                "installer_remaining_sec": self.installer_remaining_sec,
                "installer_access_status": self.installer_access_status,
                "loads": load_states,
            }
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(str(err)) from err

    def _reset_timers(self) -> None:
        self._over_limit_since = None
        self._over_warning_since = None
        self._under_restore_since = None

    async def _manage_power(self, current: float, loads: list[dict], limit_w: float, warning_w: float, restore_w: float) -> None:
        now = datetime.now()
        delay_limit = int(self.conf(CONF_DELAY_IMMEDIATE_SEC, DEFAULT_DELAY_IMMEDIATE_SEC))
        delay_warning = int(self.conf(CONF_DELAY_WARNING_SEC, DEFAULT_DELAY_WARNING_SEC))

        if current >= limit_w:
            self._over_limit_since = self._over_limit_since or now
        else:
            self._over_limit_since = None
        if current >= warning_w:
            self._over_warning_since = self._over_warning_since or now
        else:
            self._over_warning_since = None

        immediate = self._over_limit_since is not None and (now - self._over_limit_since).total_seconds() >= delay_limit
        delayed = self._over_warning_since is not None and (now - self._over_warning_since).total_seconds() >= delay_warning

        if immediate or delayed:
            await self._shed_one(loads, current, "immediato" if immediate else "ritardato")
            self._under_restore_since = None
            return

        if self._suspended and current <= restore_w:
            self._under_restore_since = self._under_restore_since or now
            wait = int(self.conf(CONF_WAIT_BEFORE_RESTORE_SEC, DEFAULT_WAIT_BEFORE_RESTORE_SEC))
            if (now - self._under_restore_since).total_seconds() >= wait:
                await self._restore_one(loads, current, restore_w)
        else:
            self._under_restore_since = None

    async def _shed_one(self, loads: list[dict], current: float, reason: str) -> None:
        now = datetime.now()
        wait = int(self.conf(CONF_WAIT_BETWEEN_SHEDS_SEC, DEFAULT_WAIT_BETWEEN_SHEDS_SEC))
        if self._last_shed and (now - self._last_shed).total_seconds() < wait:
            return
        for load in sorted(loads, key=lambda x: int(x.get(LOAD_PRIORITY, 999)), reverse=True):
            load_id = load.get(LOAD_ID)
            if not load_id or load_id in self._suspended:
                continue
            if not load.get(LOAD_ENABLED, True) or load.get(LOAD_NEVER_SHED, False):
                continue
            entity_id = load.get(LOAD_SWITCH, "")
            if not entity_id:
                continue
            power = self._load_power(load)
            if power <= float(load.get(LOAD_MIN_ACTIVE_W, 10)):
                continue
            if not self._load_is_active(load):
                continue
            if await self._call_load(load, False):
                self._suspended[load_id] = max(power, float(load.get(LOAD_ESTIMATED_W, 0) or 0), 1.0)
                self._shed_at[load_id] = now
                self._last_shed = now
                self.last_event = f"{load.get(LOAD_NAME, 'Carico')} sospeso ({reason})"
                self.hass.bus.async_fire(EVENT_LOAD_SHED, {
                    "load_id": load_id,
                    "load_name": load.get(LOAD_NAME, "Carico"),
                    "priority": load.get(LOAD_PRIORITY),
                    "power_w": self._suspended[load_id],
                    "system_power_w": current,
                    "reason": reason,
                })
                return

    async def _restore_one(self, loads: list[dict], current: float, restore_w: float) -> None:
        now = datetime.now()
        wait = int(self.conf(CONF_WAIT_BETWEEN_RESTORES_SEC, DEFAULT_WAIT_BETWEEN_RESTORES_SEC))
        if self._last_restore and (now - self._last_restore).total_seconds() < wait:
            return
        for load in sorted(loads, key=lambda x: int(x.get(LOAD_PRIORITY, 999))):
            load_id = load.get(LOAD_ID)
            if load_id not in self._suspended:
                continue
            if not load.get(LOAD_AUTO_RESTART, True):
                continue
            reserved = self._suspended[load_id]
            if current + reserved > restore_w:
                continue
            if await self._call_load(load, True):
                self._suspended.pop(load_id, None)
                self._shed_at.pop(load_id, None)
                self._last_restore = now
                self._under_restore_since = None
                self.last_event = f"{load.get(LOAD_NAME, 'Carico')} riattivato"
                self.hass.bus.async_fire(EVENT_LOAD_RESTORED, {
                    "load_id": load_id,
                    "load_name": load.get(LOAD_NAME, "Carico"),
                    "priority": load.get(LOAD_PRIORITY),
                    "restored_power_w": reserved,
                    "system_power_w": current,
                })
                return
