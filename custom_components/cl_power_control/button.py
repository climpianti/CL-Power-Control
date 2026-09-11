"""Button entities for CL Power Control."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER, NAME, VERSION


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        CLInstallerUnlockButton(coordinator, entry),
        CLInstallerLockButton(coordinator, entry),
    ])


class _CLInstallerButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        self._coordinator = coordinator
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=NAME,
            sw_version=VERSION,
        )


class CLInstallerUnlockButton(_CLInstallerButton):
    _attr_name = "Sblocca modalità installatore"
    _attr_icon = "mdi:lock-open-variant"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_installer_unlock"

    async def async_press(self) -> None:
        await self._coordinator.async_unlock_pending_installer()


class CLInstallerLockButton(_CLInstallerButton):
    _attr_name = "Blocca modalità installatore"
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_installer_lock"

    @property
    def available(self) -> bool:
        return self._coordinator.installer_unlocked

    async def async_press(self) -> None:
        self._coordinator.lock_installer()
        await self._coordinator.async_request_refresh()
