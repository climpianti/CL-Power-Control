"""CL Power Control integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, callback

from .const import (
    DOMAIN, PLATFORMS, CONF_LOADS,
    LOAD_NAME, LOAD_SWITCH, LOAD_POWER_SENSOR, LOAD_PRIORITY,
    LOAD_ENABLED, LOAD_AUTO_RESTART, LOAD_NEVER_SHED,
    LOAD_MIN_ACTIVE_W, LOAD_ESTIMATED_W, LOAD_ID,
)
from .coordinator import CLPowerControlCoordinator
from .dashboard import async_create_dashboard
from .model import new_load, normalize_priorities

SERVICE_ADD_LOAD = "add_load"
SERVICE_REMOVE_LOAD = "remove_load"


def _coordinator_for_call(hass: HomeAssistant, call: ServiceCall) -> CLPowerControlCoordinator | None:
    entry_id = str(call.data.get("entry_id", ""))
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
    return coordinator if isinstance(coordinator, CLPowerControlCoordinator) else None


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register backend actions used by the custom installer dashboard card."""
    if hass.data.setdefault(DOMAIN, {}).get("_services_registered"):
        return

    async def _add_load(call: ServiceCall) -> None:
        coordinator = _coordinator_for_call(hass, call)
        if coordinator is None:
            raise ValueError("CL Power Control configuration entry not found")
        if not coordinator.installer_unlocked:
            raise ValueError("Installer mode is locked")

        name = str(call.data["name"]).strip()[:64]
        command_entity = str(call.data["command_entity"]).strip()
        power_sensor = str(call.data.get("power_sensor", "")).strip()
        if not name or not command_entity:
            raise ValueError("Name and command entity are required")

        loads = list(coordinator.entry.data.get(CONF_LOADS, []))
        load = new_load({
            LOAD_NAME: name,
            LOAD_SWITCH: command_entity,
            LOAD_POWER_SENSOR: power_sensor,
            LOAD_PRIORITY: len(loads) + 1,
            LOAD_ENABLED: True,
            LOAD_AUTO_RESTART: True,
            LOAD_NEVER_SHED: False,
            LOAD_MIN_ACTIVE_W: 10,
            LOAD_ESTIMATED_W: 0,
        })
        loads.append(load)
        hass.config_entries.async_update_entry(
            coordinator.entry,
            data={**coordinator.entry.data, CONF_LOADS: normalize_priorities(loads)},
        )

    async def _remove_load(call: ServiceCall) -> None:
        coordinator = _coordinator_for_call(hass, call)
        if coordinator is None:
            raise ValueError("CL Power Control configuration entry not found")
        if not coordinator.installer_unlocked:
            raise ValueError("Installer mode is locked")

        load_id = str(call.data["load_id"]).strip()
        loads = list(coordinator.entry.data.get(CONF_LOADS, []))
        if not any(item.get(LOAD_ID) == load_id for item in loads):
            raise ValueError("Load not found")
        loads = [item for item in loads if item.get(LOAD_ID) != load_id]
        hass.config_entries.async_update_entry(
            coordinator.entry,
            data={**coordinator.entry.data, CONF_LOADS: normalize_priorities(loads)},
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_LOAD,
        _add_load,
        schema=vol.Schema({
            vol.Required("entry_id"): str,
            vol.Required("name"): str,
            vol.Required("command_entity"): str,
            vol.Optional("power_sensor", default=""): str,
        }),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_LOAD,
        _remove_load,
        schema=vol.Schema({
            vol.Required("entry_id"): str,
            vol.Required("load_id"): str,
        }),
    )
    hass.data[DOMAIN]["_services_registered"] = True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate older CL Power Control config entries to the current schema."""
    if entry.version > 2:
        return False

    if entry.version == 1:
        from .const import (
            CONF_ENABLED, CONF_LIMIT_W, CONF_WARNING_W, CONF_RESTORE_W,
            CONF_DELAY_IMMEDIATE_SEC, CONF_DELAY_WARNING_SEC,
            CONF_WAIT_BETWEEN_SHEDS_SEC, CONF_WAIT_BEFORE_RESTORE_SEC,
            CONF_WAIT_BETWEEN_RESTORES_SEC,
            DEFAULT_LIMIT_W, DEFAULT_WARNING_W, DEFAULT_RESTORE_W,
            DEFAULT_DELAY_IMMEDIATE_SEC, DEFAULT_DELAY_WARNING_SEC,
            DEFAULT_WAIT_BETWEEN_SHEDS_SEC, DEFAULT_WAIT_BEFORE_RESTORE_SEC,
            DEFAULT_WAIT_BETWEEN_RESTORES_SEC,
        )
        options = dict(entry.options)
        options.setdefault(CONF_ENABLED, True)
        options.setdefault(CONF_LIMIT_W, DEFAULT_LIMIT_W)
        options.setdefault(CONF_WARNING_W, DEFAULT_WARNING_W)
        options.setdefault(CONF_RESTORE_W, DEFAULT_RESTORE_W)
        options.setdefault(CONF_DELAY_IMMEDIATE_SEC, DEFAULT_DELAY_IMMEDIATE_SEC)
        options.setdefault(CONF_DELAY_WARNING_SEC, DEFAULT_DELAY_WARNING_SEC)
        options.setdefault(CONF_WAIT_BETWEEN_SHEDS_SEC, DEFAULT_WAIT_BETWEEN_SHEDS_SEC)
        options.setdefault(CONF_WAIT_BEFORE_RESTORE_SEC, DEFAULT_WAIT_BEFORE_RESTORE_SEC)
        options.setdefault(CONF_WAIT_BETWEEN_RESTORES_SEC, DEFAULT_WAIT_BETWEEN_RESTORES_SEC)
        hass.config_entries.async_update_entry(entry, options=options, version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await _async_register_services(hass)
    coordinator = CLPowerControlCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    if hass.state == CoreState.running:
        await async_create_dashboard(hass, entry)
    else:
        @callback
        def _started(_event):
            hass.async_create_task(async_create_dashboard(hass, entry))
        hass.bus.async_listen_once("homeassistant_started", _started)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
