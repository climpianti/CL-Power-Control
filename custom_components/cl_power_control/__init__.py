"""CL Power Control integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant, callback

from .const import DOMAIN, PLATFORMS
from .coordinator import CLPowerControlCoordinator
from .dashboard import async_create_dashboard


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
