"""Binary sensors for CL Power Control."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME, VERSION, LOAD_ID, LOAD_NAME, CONF_LOADS


def _device(entry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=NAME,
        sw_version=VERSION,
    )


async def async_setup_entry(hass, entry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id]
    entities = [CLInstallerModeBinarySensor(coord, entry)]
    entities.extend(
        CLLoadSuspendedBinarySensor(coord, entry, load[LOAD_ID])
        for load in entry.data.get(CONF_LOADS, [])
    )
    async_add_entities(entities)


class CLInstallerModeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Modalità installatore"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_installer_mode"
        self._attr_device_info = _device(entry)

    @property
    def is_on(self):
        return self.coordinator.installer_unlocked

    @property
    def icon(self):
        return "mdi:lock-open-variant" if self.is_on else "mdi:lock"

    @property
    def extra_state_attributes(self):
        return {"remaining_seconds": self.coordinator.installer_remaining_sec}


class CLLoadSuspendedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:power-plug-off"

    def __init__(self, coordinator, entry, load_id):
        super().__init__(coordinator)
        self._entry = entry
        self._load_id = load_id
        self._attr_unique_id = f"{entry.entry_id}_load_{load_id}_suspended"
        self._attr_device_info = _device(entry)

    def _load(self):
        if not self.coordinator.data:
            return None
        return next((x for x in self.coordinator.data.get("loads", []) if x.get(LOAD_ID) == self._load_id), None)

    @property
    def name(self):
        load = self._load()
        return f"{load.get(LOAD_NAME, 'Carico')} Sospeso" if load else "Carico Sospeso"

    @property
    def is_on(self):
        load = self._load()
        return bool(load and load.get("suspended"))

    @property
    def extra_state_attributes(self):
        load = self._load()
        if not load:
            return {}
        return {
            "priority": load.get("priority"),
            "current_power_w": load.get("current_power"),
            "switch_state": load.get("switch_state"),
            "never_shed": load.get("never_shed"),
        }
