"""Constants for CL Power Control."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "cl_power_control"
NAME = "CL Power Control"
VERSION = "0.4.0-dev.9"
MANUFACTURER = "CL Impianti"

CONF_NAME = "name"
CONF_POWER_SENSOR = "power_sensor"
CONF_LIMIT_W = "limit_w"
CONF_WARNING_W = "warning_w"
CONF_RESTORE_W = "restore_w"
CONF_DELAY_IMMEDIATE_SEC = "delay_immediate_sec"
CONF_DELAY_WARNING_SEC = "delay_warning_sec"
CONF_WAIT_BETWEEN_SHEDS_SEC = "wait_between_sheds_sec"
CONF_WAIT_BEFORE_RESTORE_SEC = "wait_before_restore_sec"
CONF_WAIT_BETWEEN_RESTORES_SEC = "wait_between_restores_sec"
CONF_LOADS = "loads"
CONF_INSTALLER_PIN_SALT = "installer_pin_salt"
CONF_INSTALLER_PIN_HASH = "installer_pin_hash"
CONF_ENABLED = "enabled"
CONF_CREATE_DASHBOARD = "create_dashboard"
CONF_ENERGY_ENABLED = "energy_enabled"
CONF_GRID_POWER_SENSOR = "grid_power_sensor"
CONF_PV_POWER_SENSOR = "pv_power_sensor"
CONF_BATTERY_POWER_SENSOR = "battery_power_sensor"
CONF_BATTERY_SOC_SENSOR = "battery_soc_sensor"
CONF_GRID_POWER_INVERT = "grid_power_invert"
CONF_BATTERY_POWER_INVERT = "battery_power_invert"
CONF_FLEX_GRID_ALLOWANCE_W = "flex_grid_allowance_w"
CONF_PREALERT_ENABLED = "prealert_enabled"
CONF_NOTIFICATION_TARGETS = "notification_targets"

LOAD_ID = "id"
LOAD_NAME = "name"
LOAD_SWITCH = "switch"
LOAD_POWER_SENSOR = "power_sensor"
LOAD_PRIORITY = "priority"
LOAD_ENABLED = "enabled"
LOAD_AUTO_RESTART = "auto_restart"
LOAD_NEVER_SHED = "never_shed"
LOAD_MIN_ACTIVE_W = "min_active_w"
LOAD_ESTIMATED_W = "estimated_w"
LOAD_ENERGY_MODE = "energy_mode"
LOAD_ENERGY_ACTION = "energy_action"
LOAD_ENERGY_TARGET_TEMP = "energy_target_temp"
LOAD_ENERGY_AUX_ENTITY = "energy_aux_entity"

ENERGY_MODE_NORMAL = "normal"
ENERGY_MODE_FLEXIBLE = "flexible"
ENERGY_MODE_SURPLUS_ONLY = "surplus_only"
ENERGY_MODE_LABELS = {
    ENERGY_MODE_NORMAL: "Normale",
    ENERGY_MODE_FLEXIBLE: "Flessibile",
    ENERGY_MODE_SURPLUS_ONLY: "Solo surplus",
}

ENERGY_ACTION_ON_OFF = "on_off"
ENERGY_ACTION_CLIMATE_COMFORT = "climate_comfort"
ENERGY_ACTION_TEMPERATURE_BOOST = "temperature_boost"
ENERGY_ACTION_AUX_HEATER = "aux_heater"
ENERGY_ACTION_LABELS = {
    ENERGY_ACTION_ON_OFF: "ON/OFF",
    ENERGY_ACTION_CLIMATE_COMFORT: "Climate - modalità comfort",
    ENERGY_ACTION_TEMPERATURE_BOOST: "Aumento temperatura",
    ENERGY_ACTION_AUX_HEATER: "Resistenza / carico ausiliario",
}

DEFAULT_LIMIT_W = 6000
DEFAULT_WARNING_W = 5500
DEFAULT_RESTORE_W = 5000
DEFAULT_DELAY_IMMEDIATE_SEC = 5
DEFAULT_DELAY_WARNING_SEC = 120
DEFAULT_WAIT_BETWEEN_SHEDS_SEC = 10
DEFAULT_WAIT_BEFORE_RESTORE_SEC = 60
DEFAULT_WAIT_BETWEEN_RESTORES_SEC = 30
DEFAULT_ENERGY_ENABLED = False
DEFAULT_GRID_POWER_INVERT = False
DEFAULT_BATTERY_POWER_INVERT = False
DEFAULT_FLEX_GRID_ALLOWANCE_W = 0
DEFAULT_LOAD_ENERGY_MODE = ENERGY_MODE_NORMAL
DEFAULT_LOAD_ENERGY_ACTION = ENERGY_ACTION_ON_OFF
DEFAULT_LOAD_ENERGY_TARGET_TEMP = 0.0
DEFAULT_PREALERT_ENABLED = False
DEFAULT_NOTIFICATION_TARGETS: list[str] = []

INSTALLER_SESSION_MINUTES = 15
UNCONFIGURED_OPTION = "Non configurato"
EVENT_LOAD_SHED = "cl_power_control_load_shed"
EVENT_LOAD_RESTORED = "cl_power_control_load_restored"
EVENT_PREALERT = "cl_power_control_prealert"
PLATFORMS = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
    Platform.TEXT,
    Platform.BUTTON,
]
