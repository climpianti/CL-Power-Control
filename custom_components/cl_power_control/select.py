"""Dashboard selectors for CL Power Control."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, MANUFACTURER, NAME, VERSION, CONF_LOADS,
    LOAD_ID, LOAD_NAME, LOAD_PRIORITY, LOAD_SWITCH, LOAD_POWER_SENSOR,
    UNCONFIGURED_OPTION,
)


def _device(entry) -> DeviceInfo:
    return DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title, manufacturer=MANUFACTURER, model=NAME, sw_version=VERSION)


def _priority_label(value: int, count: int) -> str:
    if value == 1:
        return "1 - Massima (ultimo a staccare)"
    if value == count and count > 1:
        return f"{value} - Minima (primo a staccare)"
    return str(value)


async def async_setup_entry(hass, entry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for load in entry.data.get(CONF_LOADS, []):
        load_id = load[LOAD_ID]
        entities.extend([
            CLLoadPrioritySelect(coord, entry, load_id),
            CLLoadCommandEntitySelect(coord, entry, load_id),
            CLLoadPowerSensorSelect(coord, entry, load_id),
        ])
    async_add_entities(entities)


class _CLLoadSelectBase(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, entry, load_id):
        super().__init__(coordinator)
        self._entry = entry
        self._load_id = load_id
        self._attr_device_info = _device(entry)
    def _load(self):
        if not self.coordinator.data:
            return None
        return next((x for x in self.coordinator.data.get("loads", []) if x.get(LOAD_ID) == self._load_id), None)


class CLLoadPrioritySelect(_CLLoadSelectBase):
    _attr_icon = "mdi:sort-numeric-ascending"
    def __init__(self, coordinator, entry, load_id):
        super().__init__(coordinator, entry, load_id)
        self._attr_unique_id = f"{entry.entry_id}_load_{load_id}_priority"
    @property
    def name(self):
        load = self._load()
        return f"{load.get(LOAD_NAME, 'Carico')} Priorità" if load else "Priorità"
    @property
    def options(self):
        count = max(1, len(self.coordinator.data.get("loads", [])) if self.coordinator.data else 1)
        return [_priority_label(i, count) for i in range(1, count + 1)]
    @property
    def current_option(self):
        load = self._load()
        if not load:
            return None
        count = max(1, len(self.coordinator.data.get("loads", [])))
        return _priority_label(int(load.get(LOAD_PRIORITY, 1)), count)
    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_priority(self._load_id, int(option.split(" ", 1)[0]))


class CLLoadCommandEntitySelect(_CLLoadSelectBase):
    """Installer-only selector for switch, light or climate command entity."""
    _attr_icon = "mdi:electric-switch"
    def __init__(self, coordinator, entry, load_id):
        super().__init__(coordinator, entry, load_id)
        self._attr_unique_id = f"{entry.entry_id}_load_{load_id}_command_entity"
    @property
    def name(self):
        load = self._load()
        return f"{load.get(LOAD_NAME, 'Carico')} Entità comando" if load else "Entità comando"
    @property
    def available(self) -> bool:
        return self.coordinator.installer_unlocked
    @property
    def options(self):
        choices = sorted(state.entity_id for state in self.hass.states.async_all() if state.entity_id.split(".", 1)[0] in ("switch", "light", "climate"))
        load = self._load()
        current = load.get(LOAD_SWITCH, "") if load else ""
        if current and current not in choices:
            choices.append(current)
        return [UNCONFIGURED_OPTION, *choices]
    @property
    def current_option(self):
        load = self._load()
        return load.get(LOAD_SWITCH, "") or UNCONFIGURED_OPTION if load else UNCONFIGURED_OPTION
    async def async_select_option(self, option: str) -> None:
        if self.coordinator.installer_unlocked:
            await self.coordinator.async_update_load_field(self._load_id, LOAD_SWITCH, "" if option == UNCONFIGURED_OPTION else option)


class CLLoadPowerSensorSelect(_CLLoadSelectBase):
    _attr_icon = "mdi:flash"
    def __init__(self, coordinator, entry, load_id):
        super().__init__(coordinator, entry, load_id)
        self._attr_unique_id = f"{entry.entry_id}_load_{load_id}_power_sensor"
    @property
    def name(self):
        load = self._load()
        return f"{load.get(LOAD_NAME, 'Carico')} Sensore potenza" if load else "Sensore potenza"
    @property
    def available(self) -> bool:
        return self.coordinator.installer_unlocked
    @property
    def options(self):
        choices = sorted(state.entity_id for state in self.hass.states.async_all("sensor") if state.attributes.get("device_class") == "power")
        load = self._load()
        current = load.get(LOAD_POWER_SENSOR, "") if load else ""
        if current and current not in choices:
            choices.append(current)
        return [UNCONFIGURED_OPTION, *choices]
    @property
    def current_option(self):
        load = self._load()
        return load.get(LOAD_POWER_SENSOR, "") or UNCONFIGURED_OPTION if load else UNCONFIGURED_OPTION
    async def async_select_option(self, option: str) -> None:
        if self.coordinator.installer_unlocked:
            await self.coordinator.async_update_load_field(self._load_id, LOAD_POWER_SENSOR, "" if option == UNCONFIGURED_OPTION else option)
