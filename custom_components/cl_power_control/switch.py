"""Master switch for CL Power Control."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN, NAME, VERSION, MANUFACTURER, CONF_ENABLED


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([CLPowerControlSwitch(entry)])


class CLPowerControlSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Controllo attivo"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, entry):
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title,
            manufacturer=MANUFACTURER, model=NAME, sw_version=VERSION,
        )

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
