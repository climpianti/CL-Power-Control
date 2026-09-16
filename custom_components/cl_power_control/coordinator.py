"""Load-management and energy engine for CL Power Control."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import *
from .model import move_load_to_priority, normalize_priorities
from .security import verify_pin

_LOGGER = logging.getLogger(__name__)


class CLPowerControlCoordinator(DataUpdateCoordinator[dict]):
    """Monitor power, manage loads and expose Energy Control metrics."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, logger=_LOGGER, name=f"{DOMAIN}_{entry.entry_id}", update_interval=timedelta(seconds=2))
        self.entry = entry
        self._suspended: dict[str, float] = {}
        self._shed_at: dict[str, datetime] = {}
        self._climate_restore_modes: dict[str, str] = {}
        self._over_limit_since: datetime | None = None
        self._over_warning_since: datetime | None = None
        self._under_restore_since: datetime | None = None
        self._last_shed: datetime | None = None
        self._last_restore: datetime | None = None
        self.last_event = ""
        sessions = hass.data.setdefault(DOMAIN, {}).setdefault("_installer_sessions", {})
        self._installer_sessions = sessions
        self._pending_installer_pin = ""
        self._installer_message = "Bloccato"

    @property
    def installer_unlocked(self) -> bool:
        until = self._installer_sessions.get(self.entry.entry_id)
        if until is None: return False
        if datetime.now() >= until:
            self._installer_sessions.pop(self.entry.entry_id, None); return False
        return True

    @property
    def installer_remaining_sec(self) -> int:
        until = self._installer_sessions.get(self.entry.entry_id)
        if until is None: return 0
        remaining = int((until - datetime.now()).total_seconds())
        if remaining <= 0:
            self._installer_sessions.pop(self.entry.entry_id, None); return 0
        return remaining

    def set_pending_installer_pin(self, pin: str) -> None:
        self._pending_installer_pin = str(pin or "").strip()
        self._installer_message = "PIN inserito - premi Sblocca" if self._pending_installer_pin else "Bloccato"

    @property
    def installer_access_status(self) -> str:
        if self.installer_unlocked:
            minutes, seconds = divmod(max(0, self.installer_remaining_sec), 60)
            return f"Sbloccato - {minutes}m {seconds:02d}s"
        return self._installer_message

    async def async_unlock_pending_installer(self) -> bool:
        pin = self._pending_installer_pin
        if not pin:
            self._installer_message = "Inserisci il PIN"; await self.async_request_refresh(); return False
        try: return await self.async_unlock_installer(pin)
        finally: self._pending_installer_pin = ""

    async def async_unlock_installer(self, pin: str) -> bool:
        salt = self.entry.data.get(CONF_INSTALLER_PIN_SALT, ""); digest = self.entry.data.get(CONF_INSTALLER_PIN_HASH, "")
        if not verify_pin(pin, salt, digest):
            self._installer_message = "PIN non valido"; _LOGGER.warning("Invalid installer PIN for CL Power Control"); await self.async_request_refresh(); return False
        self._installer_sessions[self.entry.entry_id] = datetime.now() + timedelta(minutes=INSTALLER_SESSION_MINUTES)
        self._installer_message = "Sbloccato"; await self.async_request_refresh(); return True

    def lock_installer(self) -> None:
        self._installer_sessions.pop(self.entry.entry_id, None); self._pending_installer_pin = ""; self._installer_message = "Bloccato"

    async def async_update_load_field(self, load_id: str, field: str, value) -> None:
        if not self.installer_unlocked: return
        allowed = {LOAD_SWITCH, LOAD_POWER_SENSOR, LOAD_ENABLED, LOAD_AUTO_RESTART, LOAD_NEVER_SHED, LOAD_MIN_ACTIVE_W, LOAD_ESTIMATED_W, LOAD_ENERGY_MODE}
        if field not in allowed: raise ValueError(f"Unsupported dashboard load field: {field}")
        if field == LOAD_ENERGY_MODE and value not in ENERGY_MODE_LABELS: value = DEFAULT_LOAD_ENERGY_MODE
        loads = [{**item, field: value} if item.get(LOAD_ID) == load_id else item for item in self.entry.data.get(CONF_LOADS, [])]
        self.hass.config_entries.async_update_entry(self.entry, data={**self.entry.data, CONF_LOADS: normalize_priorities(loads)})
        await self.async_request_refresh()

    async def async_update_global_option(self, key: str, value) -> None:
        if not self.installer_unlocked: return
        allowed = {CONF_LIMIT_W, CONF_WARNING_W, CONF_RESTORE_W, CONF_DELAY_IMMEDIATE_SEC, CONF_DELAY_WARNING_SEC, CONF_WAIT_BETWEEN_SHEDS_SEC, CONF_WAIT_BEFORE_RESTORE_SEC, CONF_WAIT_BETWEEN_RESTORES_SEC}
        if key not in allowed: raise ValueError(f"Unsupported dashboard global option: {key}")
        self.hass.config_entries.async_update_entry(self.entry, options={**self.entry.options, key: value}); await self.async_request_refresh()

    async def async_test_load(self, load_id: str, turn_on: bool) -> bool:
        if not self.installer_unlocked: return False
        load = next((x for x in self.entry.data.get(CONF_LOADS, []) if x.get(LOAD_ID) == load_id), None)
        if not load: return False
        ok = await self._call_load(load, turn_on)
        if ok: self.last_event = f"Test {'ON' if turn_on else 'OFF'}: {load.get(LOAD_NAME, 'Carico')}"; await self.async_request_refresh()
        return ok

    def conf(self, key: str, default=None):
        if key in self.entry.options: return self.entry.options[key]
        return self.entry.data.get(key, default)

    def _read_float(self, entity_id: str) -> float | None:
        if not entity_id: return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""): return None
        try: return float(state.state)
        except (TypeError, ValueError): return None

    def _entity_domain(self, entity_id: str) -> str: return entity_id.split(".", 1)[0] if entity_id and "." in entity_id else ""

    def _load_is_active(self, load: dict) -> bool:
        entity_id = load.get(LOAD_SWITCH, ""); state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in ("unknown", "unavailable", "", "off"): return False
        if self._entity_domain(entity_id) == "climate": return str(state.attributes.get("hvac_action", "")).lower() not in ("off", "idle")
        return state.state == "on"

    def _load_power(self, load: dict) -> float:
        measured = self._read_float(load.get(LOAD_POWER_SENSOR, ""))
        if measured is not None: return measured
        if not self._load_is_active(load): return 0.0
        return float(load.get(LOAD_ESTIMATED_W, 0) or 0)

    def _switch_state(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id) if entity_id else None; return state.state if state else "unknown"

    def _energy_metrics(self) -> dict:
        enabled=bool(self.conf(CONF_ENERGY_ENABLED,DEFAULT_ENERGY_ENABLED)); grid_id=self.conf(CONF_GRID_POWER_SENSOR,""); pv_id=self.conf(CONF_PV_POWER_SENSOR,""); battery_id=self.conf(CONF_BATTERY_POWER_SENSOR,""); soc_id=self.conf(CONF_BATTERY_SOC_SENSOR,"")
        grid=self._read_float(grid_id); pv=self._read_float(pv_id); battery=self._read_float(battery_id); soc=self._read_float(soc_id)
        if grid is not None and bool(self.conf(CONF_GRID_POWER_INVERT,DEFAULT_GRID_POWER_INVERT)): grid*=-1
        if battery is not None and bool(self.conf(CONF_BATTERY_POWER_INVERT,DEFAULT_BATTERY_POWER_INVERT)): battery*=-1
        configured={"grid":bool(grid_id),"pv":bool(pv_id),"battery":bool(battery_id),"soc":bool(soc_id)}
        available={"grid":grid is not None if configured["grid"] else None,"pv":pv is not None if configured["pv"] else None,"battery":battery is not None if configured["battery"] else None,"soc":soc is not None if configured["soc"] else None}
        required_values_ok=all(value is not False for key,value in available.items() if configured[key])
        grid_v=grid if grid is not None else 0.0; pv_v=max(0.0,pv) if pv is not None else 0.0; battery_v=battery if battery is not None else 0.0
        import_w=max(grid_v,0.0) if grid is not None else None; export_w=max(-grid_v,0.0) if grid is not None else None; battery_discharge_w=max(battery_v,0.0) if battery is not None else None; battery_charge_w=max(-battery_v,0.0) if battery is not None else None
        home_w=None
        if enabled and required_values_ok and (configured["grid"] or configured["pv"] or configured["battery"]): home_w=max(0.0,pv_v+grid_v+battery_v)
        surplus_w=export_w if enabled else None; status="Disattivato"
        if enabled:
            if not any(configured.values()): status="Da configurare"
            elif not required_values_ok: status="Sensore non disponibile"
            else: status="Attivo"
        return {"energy_enabled":enabled,"energy_status":status,"energy_grid_power":round(grid,1) if grid is not None else None,"energy_pv_power":round(pv_v,1) if pv is not None else None,"energy_battery_power":round(battery,1) if battery is not None else None,"energy_battery_soc":round(soc,1) if soc is not None else None,"energy_home_power":round(home_w,1) if home_w is not None else None,"energy_import_power":round(import_w,1) if import_w is not None else None,"energy_export_power":round(export_w,1) if export_w is not None else None,"energy_surplus_power":round(surplus_w,1) if surplus_w is not None else None,"energy_battery_charge_power":round(battery_charge_w,1) if battery_charge_w is not None else None,"energy_battery_discharge_power":round(battery_discharge_w,1) if battery_discharge_w is not None else None}

    async def _call_entity(self, entity_id: str, turn_on: bool) -> bool:
        if not entity_id or "." not in entity_id: return False
        domain=self._entity_domain(entity_id); service="turn_on" if turn_on else "turn_off"
        if not self.hass.services.has_service(domain,service): return False
        try: await self.hass.services.async_call(domain,service,{"entity_id":entity_id},blocking=True); return True
        except Exception as err: _LOGGER.error("Failed %s.%s on %s: %s",domain,service,entity_id,err); return False

    async def _call_climate(self, load: dict, turn_on: bool) -> bool:
        entity_id=load.get(LOAD_SWITCH,""); load_id=str(load.get(LOAD_ID,"")); state=self.hass.states.get(entity_id) if entity_id else None
        if state is None: return False
        hvac_modes=[str(mode) for mode in state.attributes.get("hvac_modes",[])]; current_mode=str(state.state or "")
        if not turn_on:
            if current_mode not in ("","off","unknown","unavailable"): self._climate_restore_modes[load_id]=current_mode
            if "off" in hvac_modes and self.hass.services.has_service("climate","set_hvac_mode"): service,data="set_hvac_mode",{"entity_id":entity_id,"hvac_mode":"off"}
            elif self.hass.services.has_service("climate","turn_off"): service,data="turn_off",{"entity_id":entity_id}
            elif self.hass.services.has_service("climate","set_hvac_mode"): service,data="set_hvac_mode",{"entity_id":entity_id,"hvac_mode":"off"}
            else: return False
        else:
            restore_mode=self._climate_restore_modes.get(load_id,"")
            if restore_mode and restore_mode!="off" and (not hvac_modes or restore_mode in hvac_modes) and self.hass.services.has_service("climate","set_hvac_mode"): service,data="set_hvac_mode",{"entity_id":entity_id,"hvac_mode":restore_mode}
            elif self.hass.services.has_service("climate","turn_on"): service,data="turn_on",{"entity_id":entity_id}
            else:
                preferred=("auto","heat_cool","cool","heat","dry","fan_only"); fallback=next((mode for mode in preferred if mode in hvac_modes),next((mode for mode in hvac_modes if mode!="off"),""))
                if not fallback or not self.hass.services.has_service("climate","set_hvac_mode"): return False
                service,data="set_hvac_mode",{"entity_id":entity_id,"hvac_mode":fallback}
        try:
            await self.hass.services.async_call("climate",service,data,blocking=True)
            if turn_on: self._climate_restore_modes.pop(load_id,None)
            return True
        except Exception as err: _LOGGER.error("Failed climate.%s on %s: %s",service,entity_id,err); return False

    async def _call_load(self, load: dict, turn_on: bool) -> bool:
        entity_id=load.get(LOAD_SWITCH,"")
        if self._entity_domain(entity_id)=="climate": return await self._call_climate(load,turn_on)
        return await self._call_entity(entity_id,turn_on)

    async def async_set_priority(self, load_id: str, priority: int) -> None:
        loads=move_load_to_priority(list(self.entry.data.get(CONF_LOADS,[])),load_id,priority); self.hass.config_entries.async_update_entry(self.entry,data={**self.entry.data,CONF_LOADS:loads}); await self.async_request_refresh()

    async def _async_update_data(self) -> dict:
        try:
            raw_loads=normalize_priorities(list(self.entry.data.get(CONF_LOADS,[]))); global_power=self._read_float(self.conf(CONF_POWER_SENSOR,"")); virtual_total=sum(self._load_power(load) for load in raw_loads); current=global_power if global_power is not None else virtual_total
            limit_w=float(self.conf(CONF_LIMIT_W,DEFAULT_LIMIT_W)); warning_w=float(self.conf(CONF_WARNING_W,DEFAULT_WARNING_W)); restore_w=float(self.conf(CONF_RESTORE_W,DEFAULT_RESTORE_W)); enabled=bool(self.conf(CONF_ENABLED,True))
            if enabled: await self._manage_power(current,raw_loads,limit_w,warning_w,restore_w)
            else: self._reset_timers()
            load_states=[]
            for load in raw_loads:
                load_id=load[LOAD_ID]; power=self._load_power(load); switch_state=self._switch_state(load.get(LOAD_SWITCH,"")); suspended=load_id in self._suspended
                if suspended and self._load_is_active(load) and power>float(load.get(LOAD_MIN_ACTIVE_W,10)): self._suspended.pop(load_id,None); self._shed_at.pop(load_id,None); suspended=False
                load_states.append({**load,"current_power":power,"switch_state":switch_state,"suspended":suspended,"suspended_power":self._suspended.get(load_id,0.0)})
            data={"current_power":round(current,1),"source":"global" if global_power is not None else "virtual","limit_w":limit_w,"warning_w":warning_w,"restore_w":restore_w,"headroom_w":round(limit_w-current,1),"load_count":len(raw_loads),"suspended_count":len(self._suspended),"suspended_power":round(sum(self._suspended.values()),1),"enabled":enabled,"last_event":self.last_event,"installer_unlocked":self.installer_unlocked,"installer_remaining_sec":self.installer_remaining_sec,"installer_access_status":self.installer_access_status,"loads":load_states}; data.update(self._energy_metrics()); return data
        except Exception as err: raise UpdateFailed(str(err)) from err

    def _reset_timers(self) -> None: self._over_limit_since=None; self._over_warning_since=None; self._under_restore_since=None

    async def _manage_power(self,current:float,loads:list[dict],limit_w:float,warning_w:float,restore_w:float)->None:
        now=datetime.now(); delay_limit=int(self.conf(CONF_DELAY_IMMEDIATE_SEC,DEFAULT_DELAY_IMMEDIATE_SEC)); delay_warning=int(self.conf(CONF_DELAY_WARNING_SEC,DEFAULT_DELAY_WARNING_SEC))
        self._over_limit_since=self._over_limit_since or now if current>=limit_w else None; self._over_warning_since=self._over_warning_since or now if current>=warning_w else None
        immediate=self._over_limit_since is not None and (now-self._over_limit_since).total_seconds()>=delay_limit; delayed=self._over_warning_since is not None and (now-self._over_warning_since).total_seconds()>=delay_warning
        if immediate or delayed: await self._shed_one(loads,current,"immediato" if immediate else "ritardato"); self._under_restore_since=None; return
        if self._suspended and current<=restore_w:
            self._under_restore_since=self._under_restore_since or now; wait=int(self.conf(CONF_WAIT_BEFORE_RESTORE_SEC,DEFAULT_WAIT_BEFORE_RESTORE_SEC))
            if (now-self._under_restore_since).total_seconds()>=wait: await self._restore_one(loads,current,restore_w)
        else: self._under_restore_since=None

    async def _shed_one(self,loads:list[dict],current:float,reason:str)->None:
        now=datetime.now(); wait=int(self.conf(CONF_WAIT_BETWEEN_SHEDS_SEC,DEFAULT_WAIT_BETWEEN_SHEDS_SEC))
        if self._last_shed and (now-self._last_shed).total_seconds()<wait: return
        for load in sorted(loads,key=lambda x:int(x.get(LOAD_PRIORITY,999)),reverse=True):
            load_id=load.get(LOAD_ID)
            if not load_id or load_id in self._suspended or not load.get(LOAD_ENABLED,True) or load.get(LOAD_NEVER_SHED,False) or not load.get(LOAD_SWITCH,""): continue
            power=self._load_power(load)
            if power<=float(load.get(LOAD_MIN_ACTIVE_W,10)) or not self._load_is_active(load): continue
            if await self._call_load(load,False):
                self._suspended[load_id]=max(power,float(load.get(LOAD_ESTIMATED_W,0) or 0),1.0); self._shed_at[load_id]=now; self._last_shed=now; self.last_event=f"{load.get(LOAD_NAME,'Carico')} sospeso ({reason})"; self.hass.bus.async_fire(EVENT_LOAD_SHED,{"load_id":load_id,"load_name":load.get(LOAD_NAME,"Carico"),"priority":load.get(LOAD_PRIORITY),"power_w":self._suspended[load_id],"system_power_w":current,"reason":reason}); return

    async def _restore_one(self,loads:list[dict],current:float,restore_w:float)->None:
        now=datetime.now(); wait=int(self.conf(CONF_WAIT_BETWEEN_RESTORES_SEC,DEFAULT_WAIT_BETWEEN_RESTORES_SEC))
        if self._last_restore and (now-self._last_restore).total_seconds()<wait: return
        for load in sorted(loads,key=lambda x:int(x.get(LOAD_PRIORITY,999))):
            load_id=load.get(LOAD_ID)
            if load_id not in self._suspended or not load.get(LOAD_AUTO_RESTART,True): continue
            reserved=self._suspended[load_id]
            if current+reserved>restore_w: continue
            if await self._call_load(load,True):
                self._suspended.pop(load_id,None); self._shed_at.pop(load_id,None); self._last_restore=now; self._under_restore_since=None; self.last_event=f"{load.get(LOAD_NAME,'Carico')} riattivato"; self.hass.bus.async_fire(EVENT_LOAD_RESTORED,{"load_id":load_id,"load_name":load.get(LOAD_NAME,"Carico"),"priority":load.get(LOAD_PRIORITY),"restored_power_w":reserved,"system_power_w":current}); return
