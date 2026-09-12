"""Button entities for CL Power Control."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME, VERSION, CONF_LOADS, LOAD_ID, LOAD_NAME


def _device(entry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=NAME,
        sw_version=VERSION,
    )


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        CLInstallerUnlockButton(coordinator, entry),
        CLInstallerLockButton(coordinator, entry),
        CLAddLoadButton(coordinator, entry),
        CLRemoveLoadButton(coordinator, entry),
    ]
    for load in entry.data.get(CONF_LOADS, []):
        load_id = load[LOAD_ID]
        entities.extend([
            CLLoadTestButton(coordinator, entry, load_id, True),
            CLLoadTestButton(coordinator, entry, load_id, False),
        ])
    async_add_entities(entities)


class _CLInstallerButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = _device(entry)


class CLInstallerUnlockButton(_CLInstallerButton):
    _attr_name = "Sblocca modalità installatore"
    _attr_icon = "mdi:lock-open-variant"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_installer_unlock"

    async def async_press(self) -> None:
        await self.coordinator.async_unlock_pending_installer()


class CLInstallerLockButton(_CLInstallerButton):
    _attr_name = "Blocca modalità installatore"
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_installer_lock"

    @property
    def available(self) -> bool:
        return self.coordinator.installer_unlocked

    async def async_press(self) -> None:
        self.coordinator.lock_installer()
        await self.coordinator.async_request_refresh()


class CLLoadTestButton(CoordinatorEntity, ButtonEntity):
    """Installer-only ON/OFF test button for a configured load."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, load_id, turn_on: bool):
        super().__init__(coordinator)
        self._entry = entry
        self._load_id = load_id
        self._turn_on = turn_on
        action = "on" if turn_on else "off"
        self._attr_unique_id = f"{entry.entry_id}_load_{load_id}_test_{action}"
        self._attr_icon = "mdi:power-on" if turn_on else "mdi:power-off"
        self._attr_device_info = _device(entry)

    def _load(self):
        if not self.coordinator.data:
            return None
        return next((x for x in self.coordinator.data.get("loads", []) if x.get(LOAD_ID) == self._load_id), None)

    @property
    def name(self):
        load = self._load()
        action = "Test ON" if self._turn_on else "Test OFF"
        return f"{load.get(LOAD_NAME, 'Carico')} {action}" if load else action

    @property
    def available(self) -> bool:
        load = self._load()
        return bool(
            self.coordinator.installer_unlocked
            and load
            and load.get("switch")
        )

    async def async_press(self) -> None:
        await self.coordinator.async_test_load(self._load_id, self._turn_on)


class CLAddLoadButton(_CLInstallerButton):
    _attr_name = "Aggiungi carico"
    _attr_icon = "mdi:plus-circle"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_installer_add_load"

    @property
    def available(self) -> bool:
        return self.coordinator.installer_unlocked

    async def async_press(self) -> None:
        await self.coordinator.async_add_pending_load()


class CLRemoveLoadButton(_CLInstallerButton):
    _attr_name = "Rimuovi carico"
    _attr_icon = "mdi:delete"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_installer_remove_load_button"

    @property
    def available(self) -> bool:
        return self.coordinator.installer_unlocked

    async def async_press(self) -> None:
        await self.coordinator.async_remove_selected_load()
