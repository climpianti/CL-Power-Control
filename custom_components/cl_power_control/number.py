"""Installer-only numeric controls for CL Power Control."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, MANUFACTURER, NAME, VERSION, CONF_LOADS,
    CONF_LIMIT_W, CONF_WARNING_W, CONF_RESTORE_W,
    CONF_DELAY_IMMEDIATE_SEC, CONF_DELAY_WARNING_SEC,
    CONF_WAIT_BETWEEN_SHEDS_SEC, CONF_WAIT_BEFORE_RESTORE_SEC,
    CONF_WAIT_BETWEEN_RESTORES_SEC,
    DEFAULT_LIMIT_W, DEFAULT_WARNING_W, DEFAULT_RESTORE_W,
    DEFAULT_DELAY_IMMEDIATE_SEC, DEFAULT_DELAY_WARNING_SEC,
    DEFAULT_WAIT_BETWEEN_SHEDS_SEC, DEFAULT_WAIT_BEFORE_RESTORE_SEC,
    DEFAULT_WAIT_BETWEEN_RESTORES_SEC,
    LOAD_ID, LOAD_NAME, LOAD_MIN_ACTIVE_W, LOAD_ESTIMATED_W,
)


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
    entities = [
        CLGlobalNumber(coord, entry, CONF_LIMIT_W, "Soglia immediata", DEFAULT_LIMIT_W, 100, 100000, 100, "W", "mdi:flash-alert"),
        CLGlobalNumber(coord, entry, CONF_WARNING_W, "Soglia ritardata", DEFAULT_WARNING_W, 0, 100000, 100, "W", "mdi:timer-alert-outline"),
        CLGlobalNumber(coord, entry, CONF_RESTORE_W, "Soglia riattivazione", DEFAULT_RESTORE_W, 0, 100000, 100, "W", "mdi:power-plug"),
        CLGlobalNumber(coord, entry, CONF_DELAY_IMMEDIATE_SEC, "Ritardo soglia immediata", DEFAULT_DELAY_IMMEDIATE_SEC, 1, 300, 1, "s", "mdi:timer-outline"),
        CLGlobalNumber(coord, entry, CONF_DELAY_WARNING_SEC, "Ritardo soglia ritardata", DEFAULT_DELAY_WARNING_SEC, 1, 10800, 1, "s", "mdi:timer-sand"),
        CLGlobalNumber(coord, entry, CONF_WAIT_BETWEEN_SHEDS_SEC, "Attesa tra distacchi", DEFAULT_WAIT_BETWEEN_SHEDS_SEC, 1, 600, 1, "s", "mdi:transmission-tower-off"),
        CLGlobalNumber(coord, entry, CONF_WAIT_BEFORE_RESTORE_SEC, "Attesa prima riattivazione", DEFAULT_WAIT_BEFORE_RESTORE_SEC, 1, 10800, 1, "s", "mdi:timer-play-outline"),
        CLGlobalNumber(coord, entry, CONF_WAIT_BETWEEN_RESTORES_SEC, "Attesa tra riattivazioni", DEFAULT_WAIT_BETWEEN_RESTORES_SEC, 1, 3600, 1, "s", "mdi:restart"),
    ]
    for load in entry.data.get(CONF_LOADS, []):
        load_id = load[LOAD_ID]
        entities.extend([
            CLLoadNumber(coord, entry, load_id, LOAD_MIN_ACTIVE_W, "Potenza minima attiva", 0, 5000, 1, "W", "mdi:flash-outline"),
            CLLoadNumber(coord, entry, load_id, LOAD_ESTIMATED_W, "Potenza stimata", 0, 100000, 10, "W", "mdi:gauge"),
        ])
    async_add_entities(entities)


class _BaseNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = _device(entry)

    @property
    def available(self) -> bool:
        return self.coordinator.installer_unlocked


class CLGlobalNumber(_BaseNumber):
    def __init__(self, coordinator, entry, key, name, default, minimum, maximum, step, unit, icon):
        super().__init__(coordinator, entry)
        self._key = key
        self._default = default
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_installer_{key}"
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def native_value(self):
        return float(self.coordinator.conf(self._key, self._default))

    async def async_set_native_value(self, value: float) -> None:
        stored = int(value) if float(value).is_integer() else float(value)
        await self.coordinator.async_update_global_option(self._key, stored)


class CLLoadNumber(_BaseNumber):
    def __init__(self, coordinator, entry, load_id, field, label, minimum, maximum, step, unit, icon):
        super().__init__(coordinator, entry)
        self._load_id = load_id
        self._field = field
        self._label = label
        self._attr_unique_id = f"{entry.entry_id}_load_{load_id}_{field}"
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    def _load(self):
        if not self.coordinator.data:
            return None
        return next((x for x in self.coordinator.data.get("loads", []) if x.get(LOAD_ID) == self._load_id), None)

    @property
    def name(self):
        load = self._load()
        return f"{load.get(LOAD_NAME, 'Carico')} {self._label}" if load else self._label

    @property
    def native_value(self):
        load = self._load()
        return float(load.get(self._field, 0)) if load else 0.0

    async def async_set_native_value(self, value: float) -> None:
        stored = int(value) if float(value).is_integer() else float(value)
        await self.coordinator.async_update_load_field(self._load_id, self._field, stored)
