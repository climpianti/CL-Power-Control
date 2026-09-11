"""Sensor entities for CL Power Control."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfPower
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME, VERSION, LOAD_ID, LOAD_NAME


def _device(entry):
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=NAME,
        sw_version=VERSION,
    )


async def async_setup_entry(hass, entry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id]
    entities = [
        CLMetricSensor(coord, entry, "current_power", "Potenza attuale", "current_power", UnitOfPower.WATT, "mdi:flash"),
        CLMetricSensor(coord, entry, "headroom", "Potenza disponibile", "headroom_w", UnitOfPower.WATT, "mdi:flash-outline"),
        CLMetricSensor(coord, entry, "suspended_power", "Potenza sospesa", "suspended_power", UnitOfPower.WATT, "mdi:pause-circle"),
        CLMetricSensor(coord, entry, "limit", "Soglia immediata", "limit_w", UnitOfPower.WATT, "mdi:flash-alert"),
        CLMetricSensor(coord, entry, "warning", "Soglia ritardata", "warning_w", UnitOfPower.WATT, "mdi:timer-alert"),
        CLMetricSensor(coord, entry, "restore", "Soglia riattivazione", "restore_w", UnitOfPower.WATT, "mdi:restart"),
        CLMetricSensor(coord, entry, "load_count", "Carichi configurati", "load_count", None, "mdi:format-list-numbered"),
        CLMetricSensor(coord, entry, "suspended_count", "Carichi sospesi", "suspended_count", None, "mdi:power-plug-off"),
        CLMetricSensor(coord, entry, "last_event", "Ultimo evento", "last_event", None, "mdi:history"),
        CLMetricSensor(coord, entry, "installer_access_status", "Stato accesso installatore", "installer_access_status", None, "mdi:shield-lock"),
    ]
    for load in entry.data.get("loads", []):
        entities.append(CLLoadPowerSensor(coord, entry, load[LOAD_ID]))
    async_add_entities(entities)


class CLMetricSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, data_key, unit, icon):
        super().__init__(coordinator)
        self._entry = entry
        self._data_key = data_key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        if unit == UnitOfPower.WATT:
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = _device(entry)

    @property
    def native_value(self):
        return self.coordinator.data.get(self._data_key) if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        if self._data_key != "current_power" or not self.coordinator.data:
            return {}
        return {
            "source": self.coordinator.data.get("source"),
            "limit_w": self.coordinator.data.get("limit_w"),
            "warning_w": self.coordinator.data.get("warning_w"),
            "restore_w": self.coordinator.data.get("restore_w"),
            "last_event": self.coordinator.data.get("last_event"),
        }


class CLLoadPowerSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:power-socket-it"

    def __init__(self, coordinator, entry, load_id):
        super().__init__(coordinator)
        self._entry = entry
        self._load_id = load_id
        self._attr_unique_id = f"{entry.entry_id}_load_{load_id}_power"
        self._attr_device_info = _device(entry)

    def _load(self):
        if not self.coordinator.data:
            return None
        return next((x for x in self.coordinator.data.get("loads", []) if x.get(LOAD_ID) == self._load_id), None)

    @property
    def name(self):
        load = self._load()
        return f"{load.get(LOAD_NAME, 'Carico')} Potenza" if load else "Carico Potenza"

    @property
    def native_value(self):
        load = self._load()
        return load.get("current_power", 0) if load else None

    @property
    def extra_state_attributes(self):
        load = self._load()
        if not load:
            return {}
        return {
            "priority": load.get("priority"),
            "switch_state": load.get("switch_state"),
            "suspended": load.get("suspended"),
            "never_shed": load.get("never_shed"),
        }
