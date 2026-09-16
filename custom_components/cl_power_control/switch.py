"""Switch entities for CL Power Control."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, NAME, VERSION, MANUFACTURER, CONF_ENABLED, CONF_LOADS,
    CONF_PREALERT_ENABLED, DEFAULT_PREALERT_ENABLED,
    LOAD_ID, LOAD_NAME, LOAD_ENABLED, LOAD_AUTO_RESTART, LOAD_NEVER_SHED,
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
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [CLPowerControlSwitch(entry), CLPrealertSwitch(entry)]
    for load in entry.data.get(CONF_LOADS, []):
        load_id = load[LOAD_ID]
        entities.extend([
            CLLoadConfigSwitch(coordinator, entry, load_id, LOAD_ENABLED, "Gestione attiva", "mdi:power"),
            CLLoadConfigSwitch(coordinator, entry, load_id, LOAD_AUTO_RESTART, "Auto riattivazione", "mdi:restart"),
            CLLoadConfigSwitch(coordinator, entry, load_id, LOAD_NEVER_SHED, "Mai distaccabile", "mdi:shield-lock"),
        ])
    async_add_entities(entities)


class CLPowerControlSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Controllo attivo"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, entry):
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_device_info = _device(entry)

    @property
    def is_on(self):
        return self._entry.options.get(CONF_ENABLED, True)

    async def async_turn_on(self, **kwargs):
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, CONF_ENABLED: True}
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, CONF_ENABLED: False}
        )
        self.async_write_ha_state()


class CLPrealertSwitch(SwitchEntity):
    """Customer-facing opt-in for pre-intervention warnings."""

    _attr_has_entity_name = True
    _attr_name = "Avviso prima del distacco"
    _attr_icon = "mdi:bell-alert-outline"

    def __init__(self, entry):
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_prealert_enabled"
        self._attr_device_info = _device(entry)

    @property
    def is_on(self):
        return bool(self._entry.options.get(CONF_PREALERT_ENABLED, DEFAULT_PREALERT_ENABLED))

    async def async_turn_on(self, **kwargs):
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_PREALERT_ENABLED: True},
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_PREALERT_ENABLED: False},
        )
        self.async_write_ha_state()


class CLLoadConfigSwitch(CoordinatorEntity, SwitchEntity):
    """Installer-only boolean setting for one managed load."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, load_id, field, label, icon):
        super().__init__(coordinator)
        self._entry = entry
        self._load_id = load_id
        self._field = field
        self._label = label
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_load_{load_id}_{field}"
        self._attr_device_info = _device(entry)

    def _load(self):
        if not self.coordinator.data:
            return None
        return next((x for x in self.coordinator.data.get("loads", []) if x.get(LOAD_ID) == self._load_id), None)

    @property
    def name(self):
        load = self._load()
        return f"{load.get(LOAD_NAME, 'Carico')} {self._label}" if load else self._label

    @property
    def available(self) -> bool:
        return self.coordinator.installer_unlocked

    @property
    def is_on(self):
        load = self._load()
        return bool(load and load.get(self._field, False))

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_update_load_field(self._load_id, self._field, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_update_load_field(self._load_id, self._field, False)
