"""Programmatic Lovelace dashboard for CL Power Control."""
from __future__ import annotations

import logging
from pathlib import Path
import shutil

from homeassistant.components import frontend
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.components.lovelace import dashboard as lv_dashboard
from homeassistant.components.lovelace.const import MODE_STORAGE, CONF_URL_PATH, CONF_ICON, CONF_TITLE, CONF_SHOW_IN_SIDEBAR, CONF_REQUIRE_ADMIN
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import storage as ha_storage

from .const import (
    DOMAIN, CONF_LOADS, LOAD_ID, LOAD_NAME, LOAD_NEVER_SHED, LOAD_PRIORITY,
    LOAD_ENERGY_MODE, LOAD_ENERGY_ACTION, LOAD_ENERGY_TARGET_TEMP,
    ENERGY_MODE_FLEXIBLE, ENERGY_MODE_SURPLUS_ONLY, ENERGY_MODE_LABELS,
    ENERGY_ACTION_LABELS, DEFAULT_LOAD_ENERGY_ACTION,
)

_LOGGER = logging.getLogger(__name__)
DASHBOARD_PATH = "cl-power-control"


async def async_install_assets(hass) -> None:
    component_dir=Path(__file__).parent; brand_dir=component_dir/"brand"; source=brand_dir/"logo.png"; header_source=brand_dir/"header_logo.png"; frontend_source=component_dir/"frontend.js"; target_dir=Path(hass.config.path("www","cl_power_control"))
    def _copy():
        if not source.exists(): raise FileNotFoundError(f"CL Power Control logo not found: {source}")
        if not frontend_source.exists(): raise FileNotFoundError(f"CL Power Control frontend not found: {frontend_source}")
        target_dir.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,target_dir/"logo.png"); shutil.copyfile(header_source if header_source.exists() else source,target_dir/"header_logo.png"); shutil.copyfile(frontend_source,target_dir/"frontend.js")
    await hass.async_add_executor_job(_copy)


def async_register_frontend_resource(hass) -> None: frontend.add_extra_js_url(hass,"/local/cl_power_control/frontend.js?v=0.4.0-dev.9")

def _dashboards(hass):
    obj=hass.data.get(LOVELACE_DOMAIN)
    if obj is None:return None
    return obj.get("dashboards") if isinstance(obj,dict) else getattr(obj,"dashboards",None)

def _eid(hass,entry,platform,unique_suffix,fallback=""):
    return er.async_get(hass).async_get_entity_id(platform,DOMAIN,f"{entry.entry_id}_{unique_suffix}") or fallback

def _header_card(title,subtitle):
    return {"type":"markdown","content":('<table role="presentation" width="100%"><tr><td width="104" valign="middle"><img src="/local/cl_power_control/header_logo.png" width="86"></td>'+f'<td valign="middle"><span style="font-size:24px"><b>{title}</b></span><br><span style="font-size:14px">{subtitle}</span></td></tr></table>')}

def _load_card(hass,entry,load):
    load_id=load[LOAD_ID]; rows=[]
    for platform,suffix,label in [("sensor",f"load_{load_id}_power","Potenza"),("select",f"load_{load_id}_priority","Priorità"),("binary_sensor",f"load_{load_id}_suspended","Sospeso")]:
        eid=_eid(hass,entry,platform,suffix)
        if eid:rows.append({"entity":eid,"name":label})
    if load.get(LOAD_NEVER_SHED,False):rows.append({"type":"section","label":"🔒 Protetto - mai distaccato"})
    return {"type":"entities","title":load.get(LOAD_NAME,"Carico"),"show_header_toggle":False,"entities":rows}

def _energy_load_card(hass,entry,load):
    load_id=load[LOAD_ID]; mode=load.get(LOAD_ENERGY_MODE); action=load.get(LOAD_ENERGY_ACTION,DEFAULT_LOAD_ENERGY_ACTION); target=float(load.get(LOAD_ENERGY_TARGET_TEMP,0) or 0); rows=[]
    power=_eid(hass,entry,"sensor",f"load_{load_id}_power"); suspended=_eid(hass,entry,"binary_sensor",f"load_{load_id}_suspended")
    if power:rows.append({"entity":power,"name":"Potenza attuale"})
    if suspended:rows.append({"entity":suspended,"name":"Sospeso da Power Control"})
    details=f"**Modalità:** {ENERGY_MODE_LABELS.get(mode,mode)}  \n**Azione:** {ENERGY_ACTION_LABELS.get(action,action)}  \n**Priorità:** {load.get(LOAD_PRIORITY,'-')}"
    if target>0:details+=f"  \n**Target energia:** {target:g} °C"
    return {"type":"vertical-stack","cards":[{"type":"markdown","content":f"### {load.get(LOAD_NAME,'Carico')}\n{details}"},{"type":"entities","show_header_toggle":False,"entities":rows}]}

def _installer_load_card(hass,entry,load):
    load_id=load[LOAD_ID]; rows=[]
    candidates=[("select",f"load_{load_id}_command_entity","Entità comando"),("select",f"load_{load_id}_power_sensor","Sensore potenza"),("select",f"load_{load_id}_priority","Priorità"),("select",f"load_{load_id}_energy_mode","Modalità energia"),("select",f"load_{load_id}_energy_action","Azione energetica"),("number",f"load_{load_id}_energy_target_temp","Temperatura target energia"),("select",f"load_{load_id}_energy_aux_entity","Entità ausiliaria energia"),("switch",f"load_{load_id}_enabled","Gestione attiva"),("switch",f"load_{load_id}_auto_restart","Auto riattivazione"),("switch",f"load_{load_id}_never_shed","Mai distaccabile"),("number",f"load_{load_id}_min_active_w","Potenza minima attiva"),("number",f"load_{load_id}_estimated_w","Potenza stimata"),("button",f"load_{load_id}_test_on","Test ON"),("button",f"load_{load_id}_test_off","Test OFF")]
    for platform,suffix,label in candidates:
        eid=_eid(hass,entry,platform,suffix)
        if eid:rows.append({"entity":eid,"name":label})
    return {"type":"entities","title":f"⚙️ {load.get(LOAD_NAME,'Carico')}","show_header_toggle":False,"entities":rows}

def _installer_global_card(hass,entry):
    rows=[]
    for platform,suffix,label in [("number","installer_limit_w","Soglia immediata"),("number","installer_warning_w","Soglia ritardata"),("number","installer_restore_w","Soglia riattivazione"),("number","installer_delay_immediate_sec","Ritardo soglia immediata"),("number","installer_delay_warning_sec","Ritardo soglia ritardata"),("number","installer_wait_between_sheds_sec","Attesa tra distacchi"),("number","installer_wait_before_restore_sec","Attesa prima riattivazione"),("number","installer_wait_between_restores_sec","Attesa tra riattivazioni")]:
        eid=_eid(hass,entry,platform,suffix)
        if eid:rows.append({"entity":eid,"name":label})
    return {"type":"entities","title":"⚙️ Parametri generali","show_header_toggle":False,"entities":rows}


def _build(hass,entry):
    def sensor(suffix):return _eid(hass,entry,"sensor",suffix)
    current=sensor("current_power") or "sensor.cl_power_control_potenza_attuale"; headroom=sensor("headroom") or "sensor.cl_power_control_potenza_disponibile"; suspended_power=sensor("suspended_power") or "sensor.cl_power_control_potenza_sospesa"; limit=sensor("limit") or "sensor.cl_power_control_soglia_immediata"; warning=sensor("warning") or "sensor.cl_power_control_soglia_ritardata"; restore=sensor("restore") or "sensor.cl_power_control_soglia_riattivazione"; last_event=sensor("last_event") or "sensor.cl_power_control_ultimo_evento"; intervention_history=sensor("intervention_history")
    enabled=_eid(hass,entry,"switch","enabled","switch.cl_power_control_controllo_attivo"); prealert=_eid(hass,entry,"switch","prealert_enabled"); installer_mode=_eid(hass,entry,"binary_sensor","installer_mode"); installer_pin=_eid(hass,entry,"text","installer_pin_entry"); installer_unlock=_eid(hass,entry,"button","installer_unlock"); installer_lock=_eid(hass,entry,"button","installer_lock"); installer_status=sensor("installer_access_status")
    energy_status=sensor("energy_status"); energy_grid=sensor("energy_grid_power"); energy_pv=sensor("energy_pv_power"); energy_home=sensor("energy_home_power"); energy_import=sensor("energy_import_power"); energy_export=sensor("energy_export_power"); energy_surplus=sensor("energy_surplus_power"); energy_battery=sensor("energy_battery_power"); energy_charge=sensor("energy_battery_charge_power"); energy_discharge=sensor("energy_battery_discharge_power"); energy_soc=sensor("energy_battery_soc"); energy_margin=sensor("energy_grid_margin"); energy_flexible=sensor("energy_flexible_available")
    loads=entry.data.get(CONF_LOADS,[]); load_cards=[_load_card(hass,entry,x) for x in loads]; installer_load_cards=[_installer_load_card(hass,entry,x) for x in loads]; flexible=[x for x in loads if x.get(LOAD_ENERGY_MODE)==ENERGY_MODE_FLEXIBLE]; surplus_only=[x for x in loads if x.get(LOAD_ENERGY_MODE)==ENERGY_MODE_SURPLUS_ONLY]; suspended_entities=[]
    for load in loads:
        eid=_eid(hass,entry,"binary_sensor",f"load_{load[LOAD_ID]}_suspended")
        if eid:suspended_entities.append({"entity":eid,"name":load.get(LOAD_NAME,"Carico")})
    overview_cards=[_header_card("CL Power Control","Gestione intelligente dei carichi e dell'energia"),{"type":"grid","columns":2,"square":False,"cards":[{"type":"tile","entity":enabled,"name":"Power Control"},{"type":"tile","entity":current,"name":"Potenza attuale"},{"type":"tile","entity":headroom,"name":"Potenza disponibile"},{"type":"tile","entity":suspended_power,"name":"Potenza sospesa"}]},{"type":"entity","entity":last_event,"name":"Ultimo intervento"},{"type":"markdown","title":"Moduli","content":"### ⚡ Power Control\nPriorità, distacco e riattivazione intelligente dei carichi.\n\n### ☀️ Energy Control\nFotovoltaico, rete, batteria e utilizzo intelligente dell'energia disponibile."}]
    power_cards=[_header_card("Power Control","Priorità e gestione automatica dei carichi"),{"type":"history-graph","title":"Andamento potenza","hours_to_show":6,"refresh_interval":15,"entities":[{"entity":current,"name":"Potenza"},{"entity":warning,"name":"Soglia ritardata"},{"entity":limit,"name":"Soglia immediata"},{"entity":restore,"name":"Riattivazione"}]}]
    if prealert:power_cards.append({"type":"entities","title":"🔔 Avvisi al cliente","show_header_toggle":False,"entities":[{"entity":prealert,"name":"Avvisami prima del distacco"}]})
    power_cards.append({"type":"markdown","content":"Con gli avvisi attivi, quando il consumo supera una soglia CL Power Control mostra un avviso prima dell'intervento automatico, lasciando il tempo di ridurre i consumi."})
    if intervention_history:power_cards.append({"type":"custom:cl-power-control-history-card","entity":intervention_history})
    power_cards.append({"type":"markdown","title":"Come funzionano le priorità","content":"**Priorità 1 = carico più importante:** ultimo a essere distaccato e primo a essere riattivato.  \nIl numero più alto identifica il carico meno importante e viene distaccato per primo."})
    if suspended_entities:power_cards.append({"type":"history-graph","title":"Storico distacco carichi","hours_to_show":12,"refresh_interval":15,"entities":suspended_entities})
    if load_cards:power_cards.append({"type":"vertical-stack","cards":[{"type":"markdown","content":"## Carichi e priorità"},*load_cards]})
    energy_cards=[_header_card("Energy Control","Fotovoltaico, rete, batteria e gestione energetica")]
    if energy_status:energy_cards.append({"type":"entity","entity":energy_status,"name":"Stato Energy Control"})
    tiles=[]
    for eid,name in [(energy_pv,"Fotovoltaico"),(energy_home,"Consumo casa"),(energy_grid,"Scambio rete"),(energy_surplus,"Surplus"),(energy_margin,"Margine contatore"),(energy_flexible,"Disponibile carichi flessibili")]:
        if eid:tiles.append({"type":"tile","entity":eid,"name":name})
    if tiles:energy_cards.append({"type":"grid","columns":2,"square":False,"cards":tiles})
    flow=[]
    for eid,name in [(energy_import,"Prelievo rete"),(energy_export,"Immissione rete"),(energy_battery,"Potenza batteria"),(energy_soc,"SOC batteria"),(energy_charge,"Carica batteria"),(energy_discharge,"Scarica batteria")]:
        if eid:flow.append({"entity":eid,"name":name})
    if flow:energy_cards.append({"type":"entities","title":"Flussi energetici","show_header_toggle":False,"entities":flow})
    if flexible:energy_cards.append({"type":"vertical-stack","cards":[{"type":"markdown","content":"## 🔄 Carichi flessibili\nPossono sfruttare l'energia disponibile secondo l'azione configurata. In questa dev la sezione è **diagnostica**: non vengono ancora comandati automaticamente."},*[_energy_load_card(hass,entry,x) for x in flexible]]})
    if surplus_only:energy_cards.append({"type":"vertical-stack","cards":[{"type":"markdown","content":"## ☀️ Carichi solo surplus\nSono destinati a usare esclusivamente energia disponibile da surplus. In questa dev la sezione è **diagnostica**: nessun comando automatico viene ancora eseguito."},*[_energy_load_card(hass,entry,x) for x in surplus_only]]})
    if not flexible and not surplus_only:energy_cards.append({"type":"markdown","title":"Carichi energetici","content":"Nessun carico classificato come **Flessibile** o **Solo surplus**. La classificazione si imposta dalla sezione Installatore."})
    graph=[]
    for eid,name in [(energy_pv,"FV"),(energy_home,"Casa"),(energy_import,"Prelievo"),(energy_export,"Immissione")]:
        if eid:graph.append({"entity":eid,"name":name})
    if graph:energy_cards.append({"type":"history-graph","title":"Andamento energia","hours_to_show":6,"refresh_interval":15,"entities":graph})
    energy_cards.append({"type":"markdown","content":"**Come funziona**  \n**Flessibile**: può utilizzare surplus e, in futuro, una quota rete configurabile.  \n**Solo surplus**: destinato a funzionare senza prelievo volontario dalla rete.  \n**Azione energetica** decide cosa fare: ON/OFF, comfort climate, aumento temperatura o resistenza/carico ausiliario.  \n\n**Convenzioni interne**  \nRete: positivo = prelievo, negativo = immissione. Batteria: positivo = scarica, negativo = carica. Il surplus corrisponde per ora alla potenza immessa in rete."})
    installer_cards=[_header_card("Installatore","Configurazione avanzata CL Power Control")]
    if installer_mode:
        locked=[]
        if installer_pin:locked.append({"entity":installer_pin,"name":"PIN installatore"})
        if installer_status:locked.append({"entity":installer_status,"name":"Stato accesso"})
        if installer_unlock:locked.append({"entity":installer_unlock,"name":"Sblocca"})
        if locked:installer_cards.append({"type":"conditional","conditions":[{"entity":installer_mode,"state":"off"}],"card":{"type":"entities","title":"🔒 Accesso installatore","show_header_toggle":False,"entities":locked}})
        unlocked=[]
        if installer_status:unlocked.append({"entity":installer_status,"name":"Sessione installatore"})
        if installer_lock:unlocked.append({"entity":installer_lock,"name":"Blocca ora"})
        if unlocked:installer_cards.append({"type":"conditional","conditions":[{"entity":installer_mode,"state":"on"}],"card":{"type":"entities","title":"🔓 Modalità installatore attiva","show_header_toggle":False,"entities":unlocked}})
        manager={"type":"custom:cl-power-control-load-manager-card","entry_id":entry.entry_id,"loads":[{"id":x.get(LOAD_ID,""),"name":x.get(LOAD_NAME,"Carico"),"priority":x.get(LOAD_PRIORITY,999)} for x in loads]}
        protected=[{"type":"markdown","content":"## Configurazione Power / Energy Control\nPer ogni carico puoi definire **Modalità energia**, **Azione energetica**, eventuale **temperatura target** ed **entità ausiliaria**. La priorità di distacco rimane indipendente."},manager,_installer_global_card(hass,entry),*installer_load_cards,{"type":"markdown","content":"## Sensori Energy Control\nPer associare rete, FV, batteria e SOC usa **Impostazioni → Dispositivi e servizi → CL Power Control → Configura → Impostazioni installatore → Energy Control**."}]
        installer_cards.append({"type":"conditional","conditions":[{"entity":installer_mode,"state":"on"}],"card":{"type":"vertical-stack","cards":protected}})
    return {"views":[{"title":"Panoramica","path":"panoramica","icon":"mdi:view-dashboard-outline","cards":overview_cards},{"title":"Power Control","path":"power-control","icon":"mdi:transmission-tower","cards":power_cards},{"title":"Energy Control","path":"energy-control","icon":"mdi:solar-power-variant","cards":energy_cards},{"title":"Installatore","path":"installatore","icon":"mdi:tools","cards":installer_cards}]}


async def async_create_dashboard(hass,entry)->None:
    try:await async_install_assets(hass);async_register_frontend_resource(hass)
    except Exception as err:_LOGGER.exception("Unable to install CL Power Control dashboard assets: %s",err);return
    dashboards=_dashboards(hass)
    if dashboards is None:_LOGGER.warning("Lovelace not ready; CL dashboard not created yet");return
    title="CL Power Control";item={"id":DASHBOARD_PATH,CONF_URL_PATH:DASHBOARD_PATH,CONF_TITLE:title,CONF_ICON:"mdi:transmission-tower",CONF_SHOW_IN_SIDEBAR:True,CONF_REQUIRE_ADMIN:False};existing=dashboards.get(DASHBOARD_PATH)
    if existing is None:
        dashboards[DASHBOARD_PATH]=lv_dashboard.LovelaceStorage(hass,item);reg_store=ha_storage.Store(hass,1,"lovelace_dashboards");data=await reg_store.async_load() or {"items":[]};data["items"]=[x for x in data.get("items",[]) if x.get("url_path")!=DASHBOARD_PATH];data["items"].append(item);await reg_store.async_save(data)
    store=dashboards.get(DASHBOARD_PATH)
    if store is None:return
    await store.async_save(_build(hass,entry))
    try:frontend.async_register_built_in_panel(hass,"lovelace",sidebar_title=title,sidebar_icon="mdi:transmission-tower",frontend_url_path=DASHBOARD_PATH,config={"mode":MODE_STORAGE},require_admin=False,update=existing is not None)
    except Exception as err:_LOGGER.debug("Sidebar registration: %s",err)
