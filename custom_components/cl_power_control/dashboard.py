"""Programmatic Lovelace dashboard for CL Power Control."""
from __future__ import annotations

import logging
from pathlib import Path
import shutil

from homeassistant.components import frontend
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.components.lovelace import dashboard as lv_dashboard
from homeassistant.components.lovelace.const import (
    MODE_STORAGE, CONF_URL_PATH, CONF_ICON, CONF_TITLE,
    CONF_SHOW_IN_SIDEBAR, CONF_REQUIRE_ADMIN,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import storage as ha_storage

from .const import DOMAIN, CONF_LOADS, LOAD_ID, LOAD_NAME, LOAD_NEVER_SHED

_LOGGER = logging.getLogger(__name__)
DASHBOARD_PATH = "cl-power-control"


async def async_install_assets(hass) -> None:
    """Expose packaged dashboard assets through /local."""
    component_dir = Path(__file__).parent
    brand_dir = component_dir / "brand"
    source = brand_dir / "logo.png"
    header_source = brand_dir / "header_logo.png"
    frontend_source = component_dir / "frontend.js"
    target_dir = Path(hass.config.path("www", "cl_power_control"))
    target = target_dir / "logo.png"
    header_target = target_dir / "header_logo.png"
    frontend_target = target_dir / "frontend.js"

    def _copy():
        if not source.exists():
            raise FileNotFoundError(f"CL Power Control logo not found: {source}")
        if not frontend_source.exists():
            raise FileNotFoundError(f"CL Power Control frontend not found: {frontend_source}")
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        shutil.copyfile(header_source if header_source.exists() else source, header_target)
        shutil.copyfile(frontend_source, frontend_target)

    await hass.async_add_executor_job(_copy)


def async_register_frontend_resource(hass) -> None:
    """Load the CL Power Control custom card as a frontend module."""
    frontend.add_extra_js_url(
        hass, "/local/cl_power_control/frontend.js?v=0.4.0-dev.1"
    )


def _dashboards(hass):
    obj = hass.data.get(LOVELACE_DOMAIN)
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get("dashboards")
    return getattr(obj, "dashboards", None)


def _eid(hass, entry, platform, unique_suffix, fallback=""):
    registry = er.async_get(hass)
    return registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{unique_suffix}") or fallback


def _header_card(title: str, subtitle: str):
    return {
        "type": "markdown",
        "content": (
            '<table role="presentation" width="100%"><tr>'
            '<td width="104" valign="middle"><img src="/local/cl_power_control/header_logo.png" width="86"></td>'
            f'<td valign="middle"><span style="font-size:24px"><b>{title}</b></span><br>'
            f'<span style="font-size:14px">{subtitle}</span></td>'
            '</tr></table>'
        ),
    }


def _load_card(hass, entry, load):
    load_id = load[LOAD_ID]
    name = load.get(LOAD_NAME, "Carico")
    priority = _eid(hass, entry, "select", f"load_{load_id}_priority")
    power = _eid(hass, entry, "sensor", f"load_{load_id}_power")
    suspended = _eid(hass, entry, "binary_sensor", f"load_{load_id}_suspended")

    rows = []
    if power:
        rows.append({"entity": power, "name": "Potenza"})
    if priority:
        rows.append({"entity": priority, "name": "Priorità"})
    if suspended:
        rows.append({"entity": suspended, "name": "Sospeso"})
    if load.get(LOAD_NEVER_SHED, False):
        rows.append({"type": "section", "label": "🔒 Protetto - mai distaccato"})

    return {"type": "entities", "title": name, "show_header_toggle": False, "entities": rows}


def _installer_load_card(hass, entry, load):
    load_id = load[LOAD_ID]
    name = load.get(LOAD_NAME, "Carico")
    rows = []
    candidates = [
        ("select", f"load_{load_id}_command_entity", "Entità comando"),
        ("select", f"load_{load_id}_power_sensor", "Sensore potenza"),
        ("select", f"load_{load_id}_priority", "Priorità"),
        ("switch", f"load_{load_id}_enabled", "Gestione attiva"),
        ("switch", f"load_{load_id}_auto_restart", "Auto riattivazione"),
        ("switch", f"load_{load_id}_never_shed", "Mai distaccabile"),
        ("number", f"load_{load_id}_min_active_w", "Potenza minima attiva"),
        ("number", f"load_{load_id}_estimated_w", "Potenza stimata"),
        ("button", f"load_{load_id}_test_on", "Test ON"),
        ("button", f"load_{load_id}_test_off", "Test OFF"),
    ]
    for platform, suffix, label in candidates:
        entity_id = _eid(hass, entry, platform, suffix)
        if entity_id:
            rows.append({"entity": entity_id, "name": label})
    return {
        "type": "entities",
        "title": f"⚙️ {name}",
        "show_header_toggle": False,
        "entities": rows,
    }


def _installer_global_card(hass, entry):
    rows = []
    candidates = [
        ("number", "installer_limit_w", "Soglia immediata"),
        ("number", "installer_warning_w", "Soglia ritardata"),
        ("number", "installer_restore_w", "Soglia riattivazione"),
        ("number", "installer_delay_immediate_sec", "Ritardo soglia immediata"),
        ("number", "installer_delay_warning_sec", "Ritardo soglia ritardata"),
        ("number", "installer_wait_between_sheds_sec", "Attesa tra distacchi"),
        ("number", "installer_wait_before_restore_sec", "Attesa prima riattivazione"),
        ("number", "installer_wait_between_restores_sec", "Attesa tra riattivazioni"),
    ]
    for platform, suffix, label in candidates:
        entity_id = _eid(hass, entry, platform, suffix)
        if entity_id:
            rows.append({"entity": entity_id, "name": label})
    return {
        "type": "entities",
        "title": "⚙️ Parametri generali",
        "show_header_toggle": False,
        "entities": rows,
    }


def _build(hass, entry):
    current = _eid(hass, entry, "sensor", "current_power", "sensor.cl_power_control_potenza_attuale")
    headroom = _eid(hass, entry, "sensor", "headroom", "sensor.cl_power_control_potenza_disponibile")
    suspended_power = _eid(hass, entry, "sensor", "suspended_power", "sensor.cl_power_control_potenza_sospesa")
    limit = _eid(hass, entry, "sensor", "limit", "sensor.cl_power_control_soglia_immediata")
    warning = _eid(hass, entry, "sensor", "warning", "sensor.cl_power_control_soglia_ritardata")
    restore = _eid(hass, entry, "sensor", "restore", "sensor.cl_power_control_soglia_riattivazione")
    last_event = _eid(hass, entry, "sensor", "last_event", "sensor.cl_power_control_ultimo_evento")
    enabled = _eid(hass, entry, "switch", "enabled", "switch.cl_power_control_controllo_attivo")
    installer_mode = _eid(hass, entry, "binary_sensor", "installer_mode")
    installer_pin = _eid(hass, entry, "text", "installer_pin_entry")
    installer_unlock = _eid(hass, entry, "button", "installer_unlock")
    installer_lock = _eid(hass, entry, "button", "installer_lock")
    installer_status = _eid(hass, entry, "sensor", "installer_access_status")

    loads = entry.data.get(CONF_LOADS, [])
    load_cards = [_load_card(hass, entry, load) for load in loads]
    installer_load_cards = [_installer_load_card(hass, entry, load) for load in loads]

    suspended_entities = []
    for load in loads:
        suspended = _eid(hass, entry, "binary_sensor", f"load_{load[LOAD_ID]}_suspended")
        if suspended:
            suspended_entities.append({"entity": suspended, "name": load.get(LOAD_NAME, "Carico")})

    overview_cards = [
        _header_card("CL Power Control", "Gestione intelligente dei carichi e dell'energia"),
        {
            "type": "grid", "columns": 2, "square": False,
            "cards": [
                {"type": "tile", "entity": enabled, "name": "Power Control"},
                {"type": "tile", "entity": current, "name": "Potenza attuale"},
                {"type": "tile", "entity": headroom, "name": "Potenza disponibile"},
                {"type": "tile", "entity": suspended_power, "name": "Potenza sospesa"},
            ],
        },
        {"type": "entity", "entity": last_event, "name": "Ultimo intervento"},
        {
            "type": "markdown",
            "title": "Moduli",
            "content": (
                "### ⚡ Power Control\n"
                "Priorità, distacco e riattivazione intelligente dei carichi.\n\n"
                "### ☀️ Energy Control\n"
                "Modulo dedicato a fotovoltaico, rete, batteria, surplus, wallbox ed EPS/generatore."
            ),
        },
    ]

    power_cards = [
        _header_card("Power Control", "Priorità e gestione automatica dei carichi"),
        {
            "type": "history-graph",
            "title": "Andamento potenza",
            "hours_to_show": 6,
            "refresh_interval": 15,
            "entities": [
                {"entity": current, "name": "Potenza"},
                {"entity": warning, "name": "Soglia ritardata"},
                {"entity": limit, "name": "Soglia immediata"},
                {"entity": restore, "name": "Riattivazione"},
            ],
        },
        {
            "type": "markdown",
            "title": "Come funzionano le priorità",
            "content": (
                "**Priorità 1 = carico più importante:** ultimo a essere distaccato e primo a essere riattivato.  \n"
                "Il numero più alto identifica il carico meno importante e viene distaccato per primo."
            ),
        },
    ]

    if suspended_entities:
        power_cards.append({
            "type": "history-graph",
            "title": "Storico distacco carichi",
            "hours_to_show": 12,
            "refresh_interval": 15,
            "entities": suspended_entities,
        })
    if load_cards:
        power_cards.append({
            "type": "vertical-stack",
            "cards": [{"type": "markdown", "content": "## Carichi e priorità"}, *load_cards],
        })

    energy_cards = [
        _header_card("Energy Control", "Fotovoltaico, rete, batteria e gestione energetica"),
        {
            "type": "markdown",
            "title": "☀️ CL Energy Control",
            "content": (
                "Questa sezione è stata predisposta come modulo separato all'interno della stessa integrazione.\n\n"
                "**Funzioni previste:**\n"
                "- Produzione fotovoltaica e scambio rete\n"
                "- Batteria e SOC\n"
                "- Surplus fotovoltaico\n"
                "- Wallbox e ricarica dinamica\n"
                "- EPS / backup / generatore\n"
                "- Scambio della potenza disponibile con Power Control\n\n"
                "Le funzioni Energy Control verranno abilitate progressivamente senza modificare il motore Power Control già collaudato."
            ),
        },
    ]

    installer_cards = [
        _header_card("Installatore", "Configurazione avanzata CL Power Control"),
    ]

    if installer_mode:
        locked_rows = []
        if installer_pin:
            locked_rows.append({"entity": installer_pin, "name": "PIN installatore"})
        if installer_status:
            locked_rows.append({"entity": installer_status, "name": "Stato accesso"})
        if installer_unlock:
            locked_rows.append({"entity": installer_unlock, "name": "Sblocca"})
        if locked_rows:
            installer_cards.append({
                "type": "conditional",
                "conditions": [{"entity": installer_mode, "state": "off"}],
                "card": {"type": "entities", "title": "🔒 Accesso installatore", "show_header_toggle": False, "entities": locked_rows},
            })

        unlocked_rows = []
        if installer_status:
            unlocked_rows.append({"entity": installer_status, "name": "Sessione installatore"})
        if installer_lock:
            unlocked_rows.append({"entity": installer_lock, "name": "Blocca ora"})
        if unlocked_rows:
            installer_cards.append({
                "type": "conditional",
                "conditions": [{"entity": installer_mode, "state": "on"}],
                "card": {"type": "entities", "title": "🔓 Modalità installatore attiva", "show_header_toggle": False, "entities": unlocked_rows},
            })

        management_card = {
            "type": "custom:cl-power-control-load-manager-card",
            "entry_id": entry.entry_id,
            "loads": [
                {
                    "id": load.get(LOAD_ID, ""),
                    "name": load.get(LOAD_NAME, "Carico"),
                    "priority": load.get("priority", 999),
                }
                for load in loads
            ],
        }

        protected_cards = [
            {
                "type": "markdown",
                "content": (
                    "## Configurazione Power Control\n"
                    "Modifica parametri e associazioni direttamente da questa sezione. "
                    "I pulsanti **Test ON/OFF** comandano realmente l'entità selezionata."
                ),
            },
            management_card,
            _installer_global_card(hass, entry),
            *installer_load_cards,
        ]
        installer_cards.append({
            "type": "conditional",
            "conditions": [{"entity": installer_mode, "state": "on"}],
            "card": {"type": "vertical-stack", "cards": protected_cards},
        })

    return {
        "views": [
            {
                "title": "Panoramica",
                "path": "panoramica",
                "icon": "mdi:view-dashboard-outline",
                "cards": overview_cards,
            },
            {
                "title": "Power Control",
                "path": "power-control",
                "icon": "mdi:transmission-tower",
                "cards": power_cards,
            },
            {
                "title": "Energy Control",
                "path": "energy-control",
                "icon": "mdi:solar-power-variant",
                "cards": energy_cards,
            },
            {
                "title": "Installatore",
                "path": "installatore",
                "icon": "mdi:tools",
                "cards": installer_cards,
            },
        ]
    }


async def async_create_dashboard(hass, entry) -> None:
    """Create or refresh a sidebar dashboard using HA storage mode."""
    try:
        await async_install_assets(hass)
        async_register_frontend_resource(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Unable to install CL Power Control dashboard assets: %s", err)
        return

    dashboards = _dashboards(hass)
    if dashboards is None:
        _LOGGER.warning("Lovelace not ready; CL dashboard not created yet")
        return

    title = "CL Power Control"
    item = {
        "id": DASHBOARD_PATH,
        CONF_URL_PATH: DASHBOARD_PATH,
        CONF_TITLE: title,
        CONF_ICON: "mdi:transmission-tower",
        CONF_SHOW_IN_SIDEBAR: True,
        CONF_REQUIRE_ADMIN: False,
    }

    existing = dashboards.get(DASHBOARD_PATH)
    if existing is None:
        dashboards[DASHBOARD_PATH] = lv_dashboard.LovelaceStorage(hass, item)
        reg_store = ha_storage.Store(hass, 1, "lovelace_dashboards")
        data = await reg_store.async_load() or {"items": []}
        data["items"] = [x for x in data.get("items", []) if x.get("url_path") != DASHBOARD_PATH]
        data["items"].append(item)
        await reg_store.async_save(data)

    store = dashboards.get(DASHBOARD_PATH)
    if store is None:
        return
    await store.async_save(_build(hass, entry))

    try:
        frontend.async_register_built_in_panel(
            hass,
            "lovelace",
            sidebar_title=title,
            sidebar_icon="mdi:transmission-tower",
            frontend_url_path=DASHBOARD_PATH,
            config={"mode": MODE_STORAGE},
            require_admin=False,
            update=existing is not None,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Sidebar registration: %s", err)
