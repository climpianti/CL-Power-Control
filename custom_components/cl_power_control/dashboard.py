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


async def async_install_logo(hass) -> None:
    """Expose the packaged CL logo through /local without manual copying."""
    brand_dir = Path(__file__).parent / "brand"
    source = brand_dir / "logo.png"
    header_source = brand_dir / "header_logo.png"
    target_dir = Path(hass.config.path("www", "cl_power_control"))
    target = target_dir / "logo.png"
    header_target = target_dir / "header_logo.png"

    def _copy():
        if not source.exists():
            raise FileNotFoundError(f"CL Power Control logo not found: {source}")
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if header_source.exists():
            shutil.copyfile(header_source, header_target)
        else:
            shutil.copyfile(source, header_target)

    await hass.async_add_executor_job(_copy)


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


def _load_card(hass, entry, load):
    load_id = load[LOAD_ID]
    name = load.get(LOAD_NAME, "Carico")
    priority = _eid(hass, entry, "select", f"load_{load_id}_priority")
    power = _eid(hass, entry, "sensor", f"load_{load_id}_power")
    suspended = _eid(hass, entry, "binary_sensor", f"load_{load_id}_suspended")

    rows = [{"type": "section", "label": "Stato carico"}]
    if power:
        rows.append({"entity": power, "name": "Potenza"})
    if priority:
        rows.append({"entity": priority, "name": "Priorità"})
    if suspended:
        rows.append({"entity": suspended, "name": "Sospeso"})
    if load.get(LOAD_NEVER_SHED, False):
        rows.append({"type": "section", "label": "🔒 Protetto - mai distaccato"})

    return {
        "type": "entities",
        "title": name,
        "show_header_toggle": False,
        "entities": rows,
    }


def _installer_load_card(hass, entry, load):
    load_id = load[LOAD_ID]
    name = load.get(LOAD_NAME, "Carico")
    command = _eid(hass, entry, "select", f"load_{load_id}_command_entity")
    power_sensor = _eid(hass, entry, "select", f"load_{load_id}_power_sensor")
    priority = _eid(hass, entry, "select", f"load_{load_id}_priority")
    rows = [{"type": "section", "label": f"Configurazione {name}"}]
    if command:
        rows.append({"entity": command, "name": "Entità comando"})
    if power_sensor:
        rows.append({"entity": power_sensor, "name": "Sensore potenza"})
    if priority:
        rows.append({"entity": priority, "name": "Priorità"})
    return {
        "type": "entities",
        "title": name,
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

    cards = [
        {
            "type": "markdown",
            "content": (
                '<table role="presentation" width="100%"><tr>'
                '<td width="118" valign="middle">'
                '<img src="/local/cl_power_control/header_logo.png" width="96">'
                '</td>'
                '<td valign="middle">'
                '<b>CL Power Control</b><br>'
                '<small>Gestione intelligente dei carichi elettrici</small>'
                '</td>'
                '</tr></table>'
            ),
        },
        {
            "type": "grid", "columns": 2, "square": False,
            "cards": [
                {"type": "tile", "entity": enabled, "name": "Controllo"},
                {"type": "tile", "entity": current, "name": "Potenza attuale"},
                {"type": "tile", "entity": headroom, "name": "Disponibile"},
                {"type": "tile", "entity": suspended_power, "name": "Sospesa"},
            ],
        },
        {
            "type": "markdown",
            "title": "Come funzionano le priorità",
            "content": (
                "**Priorità 1 = carico più importante: è l'ultimo a essere distaccato e il primo a essere riattivato.**  \n"
                "Il numero più alto identifica il carico meno importante, quindi viene distaccato per primo."
            ),
        },
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
        {"type": "entity", "entity": last_event, "name": "Ultimo intervento"},
    ]

    if suspended_entities:
        cards.append({
            "type": "history-graph",
            "title": "Storico distacco carichi",
            "hours_to_show": 12,
            "refresh_interval": 15,
            "entities": suspended_entities,
        })

    if load_cards:
        cards.append({
            "type": "vertical-stack",
            "title": "Carichi e priorità",
            "cards": load_cards,
        })

    # Installer access: show a simple locked or unlocked panel, never both.
    if installer_mode:
        locked_rows = []
        if installer_pin:
            locked_rows.append({"entity": installer_pin, "name": "PIN installatore"})
        if installer_status:
            locked_rows.append({"entity": installer_status, "name": "Stato accesso"})
        if installer_unlock:
            locked_rows.append({"entity": installer_unlock, "name": "Sblocca"})

        if locked_rows:
            cards.append({
                "type": "conditional",
                "conditions": [{"entity": installer_mode, "state": "off"}],
                "card": {
                    "type": "entities",
                    "title": "🔒 Accesso installatore",
                    "show_header_toggle": False,
                    "entities": [
                        {"type": "section", "label": "Inserisci il PIN e premi Sblocca"},
                        *locked_rows,
                    ],
                },
            })

        unlocked_rows = []
        if installer_status:
            unlocked_rows.append({"entity": installer_status, "name": "Sessione installatore"})
        if installer_lock:
            unlocked_rows.append({"entity": installer_lock, "name": "Blocca ora"})
        if unlocked_rows:
            cards.append({
                "type": "conditional",
                "conditions": [{"entity": installer_mode, "state": "on"}],
                "card": {
                    "type": "entities",
                    "title": "🔓 Modalità installatore attiva",
                    "show_header_toggle": False,
                    "entities": unlocked_rows,
                },
            })

    if installer_mode and installer_load_cards:
        cards.append({
            "type": "conditional",
            "conditions": [{"entity": installer_mode, "state": "on"}],
            "card": {
                "type": "vertical-stack",
                "cards": [
                    {
                        "type": "markdown",
                        "title": "Configurazione installatore",
                        "content": (
                            "Associa le entità direttamente dalla dashboard.  \n"
                            "Le modifiche vengono salvate nella configurazione di **CL Power Control**."
                        ),
                    },
                    *installer_load_cards,
                ],
            },
        })

    return {"views": [{
        "title": "CL Power Control",
        "path": "panoramica",
        "icon": "mdi:transmission-tower",
        "cards": cards,
    }]}


async def async_create_dashboard(hass, entry) -> None:
    """Create or refresh a sidebar dashboard using HA storage mode."""
    try:
        await async_install_logo(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Unable to install CL Power Control dashboard logo: %s", err)
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
