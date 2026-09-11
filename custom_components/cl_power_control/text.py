"""Installer PIN entry entity for CL Power Control."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER, NAME, VERSION


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CLInstallerPinText(coordinator, entry)])


class CLInstallerPinText(TextEntity):
    """Transient password field used only for installer dashboard unlock."""

    _attr_has_entity_name = True
    _attr_name = "PIN installatore"
    _attr_icon = "mdi:lock-key"
    _attr_mode = "password"
    # The entity must be allowed to have an empty state while locked.  Using a
    # minimum of 4 made Home Assistant treat the empty native value as invalid
    # and the dashboard rendered the field as non-editable.
    _attr_native_min = 0
    _attr_native_max = 12
    _attr_pattern = "[0-9]*"
    _attr_should_poll = False

    def __init__(self, coordinator, entry):
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_installer_pin_entry"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=NAME,
            sw_version=VERSION,
        )

    @property
    def native_value(self) -> str:
        # Intentionally never expose the PIN in the HA state machine.
        return ""

    async def async_set_value(self, value: str) -> None:
        # Keep the real PIN only in coordinator RAM until the unlock button is
        # pressed.  Validation is done by the coordinator, not while typing.
        self._coordinator.set_pending_installer_pin(value)
        self.async_write_ha_state()
