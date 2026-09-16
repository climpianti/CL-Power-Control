"""Sensor entities for CL Power Control."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, MANUFACTURER, NAME, VERSION, LOAD_ID, LOAD_NAME,
    CONF_FLEX_GRID_ALLOWANCE_W, DEFAULT_FLEX_GRID_ALLOWANCE_W,
)


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
        CLMetricSensor(coord, entry, "energy_status", "Energy Control Stato", "energy_status", None, "mdi:solar-power-variant"),
        CLMetricSensor(coord, entry, "energy_grid_power", "Energy Rete", "energy_grid_power", UnitOfPower.WATT, "mdi:transmission-tower"),
        CLMetricSensor(coord, entry, "energy_pv_power", "Energy Fotovoltaico", "energy_pv_power", UnitOfPower.WATT, "mdi:solar-power"),
        CLMetricSensor(coord, entry, "energy_home_power", "Energy Consumo casa", "energy_home_power", UnitOfPower.WATT, "mdi:home-lightning-bolt"),
        CLMetricSensor(coord, entry, "energy_import_power", "Energy Prelievo rete", "energy_import_power", UnitOfPower.WATT, "mdi:transmission-tower-import"),
        CLMetricSensor(coord, entry, "energy_export_power", "Energy Immissione rete", "energy_export_power", UnitOfPower.WATT, "mdi:transmission-tower-export"),
        CLMetricSensor(coord, entry, "energy_surplus_power", "Energy Surplus FV disponibile", "energy_surplus_power", UnitOfPower.WATT, "mdi:solar-power-variant-outline"),
        CLMetricSensor(coord, entry, "energy_battery_power", "Energy Batteria", "energy_battery_power", UnitOfPower.WATT, "mdi:battery-charging"),
        CLMetricSensor(coord, entry, "energy_battery_charge_power", "Energy Carica batteria", "energy_battery_charge_power", UnitOfPower.WATT, "mdi:battery-arrow-up"),
        CLMetricSensor(coord, entry, "energy_battery_discharge_power", "Energy Scarica batteria", "energy_battery_discharge_power", UnitOfPower.WATT, "mdi:battery-arrow-down"),
        CLMetricSensor(coord, entry, "energy_battery_soc", "Energy SOC batteria", "energy_battery_soc", PERCENTAGE, "mdi:battery-high"),
        CLEnergyDerivedSensor(coord, entry, "energy_grid_margin", "Energy Margine contatore", "grid_margin", "mdi:meter-electric-outline"),
        CLEnergyDerivedSensor(coord, entry, "energy_flexible_available", "Energy Disponibile carichi flessibili", "flexible_available", "mdi:power-plug-battery-outline"),
        CLInterventionHistorySensor(hass, coord, entry),
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
        elif unit == PERCENTAGE:
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = _device(entry)

    @property
    def native_value(self):
        return self.coordinator.data.get(self._data_key) if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        if self._data_key == "current_power":
            return {
                "source": self.coordinator.data.get("source"),
                "limit_w": self.coordinator.data.get("limit_w"),
                "warning_w": self.coordinator.data.get("warning_w"),
                "restore_w": self.coordinator.data.get("restore_w"),
                "last_event": self.coordinator.data.get("last_event"),
            }
        if self._data_key.startswith("energy_"):
            return {
                "energy_control_enabled": self.coordinator.data.get("energy_enabled"),
                "energy_control_status": self.coordinator.data.get("energy_status"),
            }
        return {}


class CLEnergyDerivedSensor(CoordinatorEntity, SensorEntity):
    """Derived availability values that keep Energy Control separate from load control."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator, entry, key, name, metric, icon):
        super().__init__(coordinator)
        self._entry = entry
        self._metric = metric
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = _device(entry)

    def _values(self):
        data = self.coordinator.data or {}
        if not data.get("energy_enabled") or data.get("energy_status") != "Attivo":
            return None, None, None
        grid = data.get("energy_grid_power")
        surplus = data.get("energy_surplus_power")
        limit_w = data.get("limit_w")
        if grid is None or limit_w is None:
            return None, None, None
        grid_margin = max(0.0, float(limit_w) - float(grid))
        allowance = max(0.0, float(self.coordinator.conf(CONF_FLEX_GRID_ALLOWANCE_W, DEFAULT_FLEX_GRID_ALLOWANCE_W) or 0))
        flexible = min(grid_margin, max(0.0, float(surplus or 0)) + allowance)
        return grid_margin, flexible, allowance

    @property
    def native_value(self):
        grid_margin, flexible, _ = self._values()
        value = grid_margin if self._metric == "grid_margin" else flexible
        return round(value, 1) if value is not None else None

    @property
    def extra_state_attributes(self):
        grid_margin, flexible, allowance = self._values()
        return {
            "energy_control_enabled": (self.coordinator.data or {}).get("energy_enabled"),
            "grid_margin_w": round(grid_margin, 1) if grid_margin is not None else None,
            "surplus_w": (self.coordinator.data or {}).get("energy_surplus_power"),
            "grid_allowance_w": round(allowance, 1) if allowance is not None else None,
            "flexible_available_w": round(flexible, 1) if flexible is not None else None,
        }


class CLInterventionHistorySensor(CoordinatorEntity, SensorEntity):
    """Expose persistent Power Control intervention history."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:history"

    def __init__(self, hass, coordinator, entry):
        super().__init__(coordinator)
        self._history = hass.data[DOMAIN].get(f"{entry.entry_id}_history")
        self._attr_unique_id = f"{entry.entry_id}_intervention_history"
        self._attr_name = "Storico interventi"
        self._attr_device_info = _device(entry)

    @property
    def native_value(self):
        latest = self._history.latest if self._history else None
        if not latest:
            return "Nessun intervento"
        status = "in corso" if not latest.get("ended_at") else "completato"
        return f"{latest.get('started_at', '')} - {status}"

    @property
    def extra_state_attributes(self):
        if not self._history:
            return {}
        latest = self._history.latest or {}
        return {
            "interventi_memorizzati": self._history.incident_count,
            "motivo": latest.get("reason"),
            "potenza_intervento_w": latest.get("system_power_w"),
            "soglia_w": latest.get("threshold_w"),
            "iniziato": latest.get("started_at"),
            "terminato": latest.get("ended_at"),
            "carichi_al_momento_intervento": latest.get("snapshot", []),
            "azioni_intervento": latest.get("actions", []),
            "ultimi_interventi": self._history.recent,
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
