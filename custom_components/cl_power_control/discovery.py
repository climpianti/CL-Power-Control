"""Conservative local discovery of SENEC and Solarman Home Assistant sensors.

Discovery never writes configuration, turns on load management or guesses a
bidirectional meter from an import-only/export-only entity. Roles must have
matching physical units and an explicitly identified integration platform.
"""
from __future__ import annotations

import re
from typing import Any

POWER_ROLES = ("power_sensor", "grid_power_sensor", "pv_power_sensor", "battery_power_sensor")
SOURCE_ROLES = POWER_ROLES + ("battery_soc_sensor",)
PROVIDERS = ("senec", "solarman")

# First entries are preferred when an integration exposes aliases.
PATTERNS: dict[str, dict[str, tuple[str, ...]]] = {
    "senec": {
        "power_sensor": ("senec_house_power",),
        "grid_power_sensor": ("senec_grid_state_power", "senec_enfluri_net_power_total"),
        "pv_power_sensor": ("senec_solar_generated_power",),
        "battery_power_sensor": ("senec_battery_state_power",),
        "battery_soc_sensor": ("senec_battery_charge_percent",),
    },
    "solarman": {
        "power_sensor": ("total_load_power", "load_total_power", "load_power", "house_power", "home_power", "consumption_power"),
        "grid_power_sensor": ("total_grid_power", "grid_total_power", "grid_power", "meter_power", "pcc_power", "active_power_pcc"),
        "pv_power_sensor": ("total_pv_power", "pv_total_power", "pv_power", "solar_generated_power", "total_solar_power", "solar_power", "total_dc_power"),
        "battery_power_sensor": ("battery_charge_discharge_power", "battery_state_power", "battery_power"),
        "battery_soc_sensor": ("battery_charge_percent", "battery_state_of_charge", "battery_soc", "battery_capacity"),
    },
}

# These names describe one direction, one phase or one MPPT; they must never
# silently stand in for a signed grid measurement or a total solar output.
PARTIAL_POWER = re.compile(
    r"(?:^|_)(?:pv[1-9]|mppt[1-9]|mpp[1-9]|l[1-3]|phase[1-3]|"
    r"grid_import|grid_export|imported_power|exported_power|"
    r"charge_power|discharge_power)(?:_|$)"
)

def is_internal_sensor(entity_id: str | None) -> bool:
    """Reject feedback from *any* CL Power Control derived sensor."""
    return str(entity_id or "").startswith("sensor.cl_power_control_")

def normalize_name(value: Any) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower())
    return value.strip("_")

def provider_for(row: dict) -> str | None:
    platform = normalize_name(row.get("platform"))
    if platform == "senec":
        return "senec"
    if platform.startswith("solarman") or platform in ("solarman_lse", "solarman_v5"):
        return "solarman"
    # Certain custom Solarman editions register a unique-id namespace.
    uid = normalize_name(row.get("unique_id"))
    if uid.startswith("solarman_") and row.get("platform") not in ("template", "integration"):
        return "solarman"
    return None

def valid_role_unit(row: dict, role: str) -> bool:
    unit = str(row.get("unit") or "").strip()
    dc = str(row.get("device_class") or "").lower()
    if role == "battery_soc_sensor":
        return unit in ("%", "percent") or (dc == "battery" and not unit)
    return unit in ("W", "kW") and (not dc or dc == "power")

def role_score(row: dict, provider: str, role: str) -> int:
    if not valid_role_unit(row, role):
        return 0
    full_id = normalize_name(str(row.get("entity_id", "")).removeprefix("sensor."))
    human = normalize_name(row.get("original_name") or row.get("friendly_name"))
    name = full_id.removeprefix("senec_").removeprefix("solarman_")
    variants = PATTERNS[provider][role]
    if role != "battery_soc_sensor" and (PARTIAL_POWER.search(name) or PARTIAL_POWER.search(human)):
        return 0
    for i, pattern in enumerate(variants):
        # Require a complete suffix or exact alias, avoiding e.g. pv1_power.
        if name == pattern or full_id == pattern or name.endswith("_" + pattern) or full_id.endswith("_" + pattern):
            return 200 - i * 10
        if human == pattern or human.endswith("_" + pattern):
            return 130 - i * 8
    return 0

def discover_candidates(rows: list[dict]) -> list[dict]:
    """Rank per *physical device*, never merge sensors from different inverters.

    Each input row is a registry entity plus its current state metadata.
    Disabled/unavailable sensors and sensors produced by CL Power Control
    are ignored. No write is performed.
    """
    grouped: dict[str, dict] = {}
    for row in rows:
        entity_id = str(row.get("entity_id") or "")
        if not entity_id.startswith("sensor.") or is_internal_sensor(entity_id):
            continue
        provider = provider_for(row)
        if provider is None or not row.get("enabled", True):
            continue
        # A zero is a valid measurement; unknown/unavailable is not.
        if row.get("state") in (None, "unavailable", "unknown", ""):
            continue
        device = str(row.get("device_id") or row.get("config_entry_id") or provider)
        group_key = provider + ":" + device
        group = grouped.setdefault(group_key, {
            "id": group_key, "provider": provider, "candidates": {},
            "matched": 0, "warnings": [],
        })
        for role in SOURCE_ROLES:
            rank = role_score(row, provider, role)
            if rank and rank > group["candidates"].get(role, {}).get("score", 0):
                group["candidates"][role] = {
                    "entity_id": entity_id,
                    "score": rank,
                    "unit": row.get("unit"),
                }
    found = []
    for group in grouped.values():
        group["sources"] = {key: data["entity_id"] for key, data in group["candidates"].items()}
        group["matched"] = len(group["sources"])
        if group["matched"] < 1:
            continue
        if group["provider"] == "solarman" and "grid_power_sensor" in group["sources"]:
            group["warnings"].append(
                "Solarman: verificare il segno della potenza di rete (positivo=prelievo)."
            )
        if "battery_power_sensor" in group["sources"]:
            group["warnings"].append(
                "Verificare segno batteria: positivo=scarica, negativo=carica."
            )
        if "grid_power_sensor" not in group["sources"]:
            group["warnings"].append("Nessun sensore rete bidirezionale riconosciuto.")
        found.append(group)
    return sorted(found, key=lambda g: (-g["matched"], g["provider"], g["id"]))

def proposal_for(current: dict, discovered: dict, *, replace_existing: bool = False) -> dict:
    """Patch only source links, never control enable/limits or installer secrets."""
    source_map = discovered.get("sources", {})
    changes = {}
    for role in SOURCE_ROLES:
        candidate = source_map.get(role)
        if not candidate or is_internal_sensor(candidate):
            continue
        existing = str(current.get(role) or "")
        if replace_existing or not existing or is_internal_sensor(existing):
            if existing != candidate:
                changes[role] = candidate
            # SENEC's grid_state_power is positive on import. Solarman's
            # grid polarity cannot be inferred safely from its name alone.
            if (role == "grid_power_sensor"
                and discovered.get("provider") == "senec"
                and "grid_state_power" in candidate):
                changes["grid_power_invert"] = False
    return changes

def summary(group: dict) -> str:
    order = ("power_sensor", "grid_power_sensor", "pv_power_sensor",
             "battery_power_sensor", "battery_soc_sensor")
    names = {
        "power_sensor": "Casa", "grid_power_sensor": "Rete",
        "pv_power_sensor": "FV", "battery_power_sensor": "Batteria",
        "battery_soc_sensor": "SOC",
    }
    return " | ".join(
        f"{names[role]}: {group['sources'][role]}"
        for role in order if role in group["sources"]
    )
