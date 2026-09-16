"""Config and options flow for CL Power Control."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import *
from .model import new_load, sort_loads
from .security import create_pin_hash, verify_pin


def _power_schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_POWER_SENSOR, description={"suggested_value": defaults.get(CONF_POWER_SENSOR, "")}): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
        vol.Required(CONF_LIMIT_W, default=defaults.get(CONF_LIMIT_W, DEFAULT_LIMIT_W)): NumberSelector(NumberSelectorConfig(min=100, max=100000, step=100, unit_of_measurement="W", mode=NumberSelectorMode.BOX)),
        vol.Required(CONF_WARNING_W, default=defaults.get(CONF_WARNING_W, DEFAULT_WARNING_W)): NumberSelector(NumberSelectorConfig(min=0, max=100000, step=100, unit_of_measurement="W", mode=NumberSelectorMode.BOX)),
        vol.Required(CONF_RESTORE_W, default=defaults.get(CONF_RESTORE_W, DEFAULT_RESTORE_W)): NumberSelector(NumberSelectorConfig(min=0, max=100000, step=100, unit_of_measurement="W", mode=NumberSelectorMode.BOX)),
    })


def _energy_schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_ENERGY_ENABLED, default=defaults.get(CONF_ENERGY_ENABLED, DEFAULT_ENERGY_ENABLED)): BooleanSelector(),
        vol.Optional(CONF_GRID_POWER_SENSOR, description={"suggested_value": defaults.get(CONF_GRID_POWER_SENSOR, "")}): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
        vol.Required(CONF_GRID_POWER_INVERT, default=defaults.get(CONF_GRID_POWER_INVERT, DEFAULT_GRID_POWER_INVERT)): BooleanSelector(),
        vol.Optional(CONF_PV_POWER_SENSOR, description={"suggested_value": defaults.get(CONF_PV_POWER_SENSOR, "")}): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
        vol.Optional(CONF_BATTERY_POWER_SENSOR, description={"suggested_value": defaults.get(CONF_BATTERY_POWER_SENSOR, "")}): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
        vol.Required(CONF_BATTERY_POWER_INVERT, default=defaults.get(CONF_BATTERY_POWER_INVERT, DEFAULT_BATTERY_POWER_INVERT)): BooleanSelector(),
        vol.Optional(CONF_BATTERY_SOC_SENSOR, description={"suggested_value": defaults.get(CONF_BATTERY_SOC_SENSOR, "")}): EntitySelector(EntitySelectorConfig(domain="sensor")),
    })


def _timing_schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_DELAY_IMMEDIATE_SEC, default=defaults.get(CONF_DELAY_IMMEDIATE_SEC, DEFAULT_DELAY_IMMEDIATE_SEC)): NumberSelector(NumberSelectorConfig(min=1, max=300, step=1, unit_of_measurement="s", mode=NumberSelectorMode.BOX)),
        vol.Required(CONF_DELAY_WARNING_SEC, default=defaults.get(CONF_DELAY_WARNING_SEC, DEFAULT_DELAY_WARNING_SEC)): NumberSelector(NumberSelectorConfig(min=1, max=10800, step=1, unit_of_measurement="s", mode=NumberSelectorMode.BOX)),
        vol.Required(CONF_WAIT_BETWEEN_SHEDS_SEC, default=defaults.get(CONF_WAIT_BETWEEN_SHEDS_SEC, DEFAULT_WAIT_BETWEEN_SHEDS_SEC)): NumberSelector(NumberSelectorConfig(min=1, max=600, step=1, unit_of_measurement="s", mode=NumberSelectorMode.BOX)),
        vol.Required(CONF_WAIT_BEFORE_RESTORE_SEC, default=defaults.get(CONF_WAIT_BEFORE_RESTORE_SEC, DEFAULT_WAIT_BEFORE_RESTORE_SEC)): NumberSelector(NumberSelectorConfig(min=1, max=10800, step=1, unit_of_measurement="s", mode=NumberSelectorMode.BOX)),
        vol.Required(CONF_WAIT_BETWEEN_RESTORES_SEC, default=defaults.get(CONF_WAIT_BETWEEN_RESTORES_SEC, DEFAULT_WAIT_BETWEEN_RESTORES_SEC)): NumberSelector(NumberSelectorConfig(min=1, max=3600, step=1, unit_of_measurement="s", mode=NumberSelectorMode.BOX)),
    })


def _load_schema(defaults: dict | None = None) -> vol.Schema:
    defaults = defaults or {}
    energy_options = [
        {"value": mode, "label": label}
        for mode, label in ENERGY_MODE_LABELS.items()
    ]
    return vol.Schema({
        vol.Required(LOAD_NAME, default=defaults.get(LOAD_NAME, "Nuovo carico")): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Optional(LOAD_SWITCH, description={"suggested_value": defaults.get(LOAD_SWITCH, "")}): EntitySelector(EntitySelectorConfig(domain=["switch", "light", "climate"])),
        vol.Optional(LOAD_POWER_SENSOR, description={"suggested_value": defaults.get(LOAD_POWER_SENSOR, "")}): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
        vol.Required(LOAD_PRIORITY, default=defaults.get(LOAD_PRIORITY, 1)): NumberSelector(NumberSelectorConfig(min=1, max=100, step=1, mode=NumberSelectorMode.BOX)),
        vol.Required(LOAD_ENERGY_MODE, default=defaults.get(LOAD_ENERGY_MODE, DEFAULT_LOAD_ENERGY_MODE)): SelectSelector(SelectSelectorConfig(options=energy_options, mode=SelectSelectorMode.DROPDOWN)),
        vol.Required(LOAD_ENABLED, default=defaults.get(LOAD_ENABLED, True)): BooleanSelector(),
        vol.Required(LOAD_AUTO_RESTART, default=defaults.get(LOAD_AUTO_RESTART, True)): BooleanSelector(),
        vol.Required(LOAD_NEVER_SHED, default=defaults.get(LOAD_NEVER_SHED, False)): BooleanSelector(),
        vol.Required(LOAD_MIN_ACTIVE_W, default=defaults.get(LOAD_MIN_ACTIVE_W, 10)): NumberSelector(NumberSelectorConfig(min=0, max=5000, step=1, unit_of_measurement="W", mode=NumberSelectorMode.BOX)),
        vol.Required(LOAD_ESTIMATED_W, default=defaults.get(LOAD_ESTIMATED_W, 0)): NumberSelector(NumberSelectorConfig(min=0, max=100000, step=10, unit_of_measurement="W", mode=NumberSelectorMode.BOX)),
    })


class CLPowerControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            pin = user_input.pop("installer_pin")
            confirm = user_input.pop("installer_pin_confirm")
            if len(pin) < 4 or not pin.isdigit():
                errors["installer_pin"] = "pin_format"
            elif pin != confirm:
                errors["installer_pin_confirm"] = "pin_mismatch"
            else:
                salt, digest = create_pin_hash(pin)
                data = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_INSTALLER_PIN_SALT: salt,
                    CONF_INSTALLER_PIN_HASH: digest,
                    CONF_LOADS: [],
                }
                options = {
                    CONF_ENABLED: True,
                    CONF_LIMIT_W: DEFAULT_LIMIT_W,
                    CONF_WARNING_W: DEFAULT_WARNING_W,
                    CONF_RESTORE_W: DEFAULT_RESTORE_W,
                    CONF_DELAY_IMMEDIATE_SEC: DEFAULT_DELAY_IMMEDIATE_SEC,
                    CONF_DELAY_WARNING_SEC: DEFAULT_DELAY_WARNING_SEC,
                    CONF_WAIT_BETWEEN_SHEDS_SEC: DEFAULT_WAIT_BETWEEN_SHEDS_SEC,
                    CONF_WAIT_BEFORE_RESTORE_SEC: DEFAULT_WAIT_BEFORE_RESTORE_SEC,
                    CONF_WAIT_BETWEEN_RESTORES_SEC: DEFAULT_WAIT_BETWEEN_RESTORES_SEC,
                    CONF_ENERGY_ENABLED: DEFAULT_ENERGY_ENABLED,
                    CONF_PREALERT_ENABLED: DEFAULT_PREALERT_ENABLED,
                    CONF_NOTIFICATION_TARGETS: DEFAULT_NOTIFICATION_TARGETS,
                }
                return self.async_create_entry(title=user_input[CONF_NAME], data=data, options=options)

        schema = vol.Schema({
            vol.Required(CONF_NAME, default=NAME): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required("installer_pin"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required("installer_pin_confirm"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CLPowerControlOptionsFlow(config_entry)


class CLPowerControlOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._data = {**config_entry.data, **config_entry.options}
        self._selected_load_id = None
        self._installer_unlocked = False

    def _shared_installer_unlocked(self):
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        return bool(self._installer_unlocked or (coordinator and coordinator.installer_unlocked))

    def _mobile_services(self):
        services = self.hass.services.async_services().get("notify", {})
        return {
            f"notify.{name}": name.replace("mobile_app_", "").replace("_", " ").title()
            for name in services
            if name.startswith("mobile_app_")
        }

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["quick", "notifications", "loads", "installer_unlock", "installer_pin_reset"])

    async def async_step_quick(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self._save()
        return self.async_show_form(step_id="quick", data_schema=_power_schema(self._data))

    async def async_step_notifications(self, user_input=None):
        choices = self._mobile_services()
        if user_input is not None:
            self._data[CONF_NOTIFICATION_TARGETS] = list(user_input.get(CONF_NOTIFICATION_TARGETS, []))
            return await self._save()
        current = [x for x in self._data.get(CONF_NOTIFICATION_TARGETS, []) if x in choices]
        schema = vol.Schema({vol.Optional(CONF_NOTIFICATION_TARGETS, default=current): vol.All([vol.In(choices)])})
        return self.async_show_form(step_id="notifications", data_schema=schema, description_placeholders={"devices": str(len(choices))})

    async def async_step_loads(self, user_input=None):
        loads = sort_loads(list(self._data.get(CONF_LOADS, [])))
        options = ["load_add"]
        if loads:
            options.extend(["load_select", "load_delete"])
        options.append("init")
        return self.async_show_menu(step_id="loads", menu_options=options)

    async def async_step_load_add(self, user_input=None):
        if user_input is not None:
            loads = list(self._data.get(CONF_LOADS, []))
            loads.append(new_load(user_input))
            self._data[CONF_LOADS] = sort_loads(loads)
            return await self._save()
        defaults = {
            LOAD_PRIORITY: len(self._data.get(CONF_LOADS, [])) + 1,
            LOAD_ENERGY_MODE: DEFAULT_LOAD_ENERGY_MODE,
        }
        return self.async_show_form(step_id="load_add", data_schema=_load_schema(defaults))

    async def async_step_load_select(self, user_input=None):
        loads = sort_loads(list(self._data.get(CONF_LOADS, [])))
        if user_input is not None:
            self._selected_load_id = user_input["load_id"]
            return await self.async_step_load_edit()
        choices = {i[LOAD_ID]: f"P{i.get(LOAD_PRIORITY, '?')} - {i.get(LOAD_NAME, 'Carico')}" for i in loads}
        return self.async_show_form(step_id="load_select", data_schema=vol.Schema({vol.Required("load_id"): vol.In(choices)}))

    async def async_step_load_edit(self, user_input=None):
        loads = list(self._data.get(CONF_LOADS, []))
        current = next((x for x in loads if x.get(LOAD_ID) == self._selected_load_id), None)
        if current is None:
            return await self.async_step_loads()
        if user_input is not None:
            updated = {**current, **user_input, LOAD_ID: current[LOAD_ID]}
            self._data[CONF_LOADS] = sort_loads([updated if x.get(LOAD_ID) == current[LOAD_ID] else x for x in loads])
            return await self._save()
        return self.async_show_form(step_id="load_edit", data_schema=_load_schema(current))

    async def async_step_load_delete(self, user_input=None):
        loads = sort_loads(list(self._data.get(CONF_LOADS, [])))
        choices = {i[LOAD_ID]: f"P{i.get(LOAD_PRIORITY, '?')} - {i.get(LOAD_NAME, 'Carico')}" for i in loads}
        if user_input is not None:
            self._data[CONF_LOADS] = sort_loads([x for x in loads if x.get(LOAD_ID) != user_input["load_id"]])
            return await self._save()
        return self.async_show_form(step_id="load_delete", data_schema=vol.Schema({vol.Required("load_id"): vol.In(choices)}))

    async def async_step_installer_pin_reset(self, user_input=None):
        errors = {}
        if user_input is not None:
            pin = str(user_input["new_pin"]).strip()
            confirm = str(user_input["confirm_pin"]).strip()
            if len(pin) < 4 or not pin.isdigit():
                errors["new_pin"] = "pin_format"
            elif pin != confirm:
                errors["confirm_pin"] = "pin_mismatch"
            else:
                salt, digest = create_pin_hash(pin)
                self._data[CONF_INSTALLER_PIN_SALT] = salt
                self._data[CONF_INSTALLER_PIN_HASH] = digest
                self._installer_unlocked = False
                return await self._save()
        return self.async_show_form(step_id="installer_pin_reset", data_schema=vol.Schema({
            vol.Required("new_pin"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required("confirm_pin"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }), errors=errors)

    async def async_step_installer_unlock(self, user_input=None):
        if self._shared_installer_unlocked():
            return await self.async_step_installer()
        errors = {}
        if user_input is not None:
            if verify_pin(user_input["pin"], self._data.get(CONF_INSTALLER_PIN_SALT, ""), self._data.get(CONF_INSTALLER_PIN_HASH, "")):
                self._installer_unlocked = True
                coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
                if coordinator is not None:
                    await coordinator.async_unlock_installer(user_input["pin"])
                return await self.async_step_installer()
            errors["base"] = "invalid_pin"
        return self.async_show_form(step_id="installer_unlock", data_schema=vol.Schema({vol.Required("pin"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}), errors=errors)

    async def async_step_installer(self, user_input=None):
        if not self._shared_installer_unlocked():
            return await self.async_step_installer_unlock()
        return self.async_show_menu(step_id="installer", menu_options=["loads", "installer_power", "installer_energy", "installer_timing", "installer_pin_change", "init"])

    async def async_step_installer_power(self, user_input=None):
        if not self._shared_installer_unlocked():
            return await self.async_step_installer_unlock()
        if user_input is not None:
            self._data.update(user_input)
            return await self._save()
        return self.async_show_form(step_id="installer_power", data_schema=_power_schema(self._data))

    async def async_step_installer_energy(self, user_input=None):
        if not self._shared_installer_unlocked():
            return await self.async_step_installer_unlock()
        if user_input is not None:
            self._data.update(user_input)
            return await self._save()
        return self.async_show_form(step_id="installer_energy", data_schema=_energy_schema(self._data))

    async def async_step_installer_timing(self, user_input=None):
        if not self._shared_installer_unlocked():
            return await self.async_step_installer_unlock()
        if user_input is not None:
            self._data.update(user_input)
            return await self._save()
        return self.async_show_form(step_id="installer_timing", data_schema=_timing_schema(self._data))

    async def async_step_installer_pin_change(self, user_input=None):
        if not self._shared_installer_unlocked():
            return await self.async_step_installer_unlock()
        errors = {}
        if user_input is not None:
            pin = user_input["new_pin"]
            if len(pin) < 4 or not pin.isdigit():
                errors["new_pin"] = "pin_format"
            elif pin != user_input["confirm_pin"]:
                errors["confirm_pin"] = "pin_mismatch"
            else:
                salt, digest = create_pin_hash(pin)
                self._data[CONF_INSTALLER_PIN_SALT] = salt
                self._data[CONF_INSTALLER_PIN_HASH] = digest
                return await self._save()
        return self.async_show_form(step_id="installer_pin_change", data_schema=vol.Schema({
            vol.Required("new_pin"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required("confirm_pin"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }), errors=errors)

    async def _save(self):
        persistent_keys = {CONF_NAME, CONF_INSTALLER_PIN_SALT, CONF_INSTALLER_PIN_HASH, CONF_LOADS}
        data = {k: v for k, v in self._data.items() if k in persistent_keys}
        options = {k: v for k, v in self._data.items() if k not in persistent_keys}
        self.hass.config_entries.async_update_entry(self.config_entry, data=data, options=options)
        return self.async_create_entry(title="", data=options)
