"""Read-only source diagnostics for the CL Power Control installer.

No thresholds, loads, polarity flags or entity configuration are changed here.
The energy balance is only a snapshot hint, not an automatic polarity detector.
"""
from __future__ import annotations

import math

from .discovery import SOURCE_ROLES, is_internal_sensor, provider_for, valid_role_unit

LABELS = {
    "power_sensor": "Potenza generale",
    "grid_power_sensor": "Rete",
    "pv_power_sensor": "Fotovoltaico",
    "battery_power_sensor": "Batteria",
    "battery_soc_sensor": "SOC",
}

def inspect_sources(rows: list[dict], config: dict, groups: list[dict]) -> dict:
    """Inspect configured sensors and optionally compare a native house meter.

    A balance check is allowed only when the native house meter and all
    configured FV/grid/battery sources belong to the *same* discovered device.
    It is advisory: samples are not guaranteed to be synchronous.
    """
    registry = {str(row.get("entity_id")): row for row in rows}
    sources: dict[str, dict] = {}
    warnings: list[str] = []
    for role in SOURCE_ROLES:
        entity_id = str(config.get(role) or "")
        info = {"entity_id": entity_id, "status": "Non configurato", "value": None,
                "unit": "%" if role == "battery_soc_sensor" else "W",
                "provider": None}
        if entity_id:
            row = registry.get(entity_id)
            if is_internal_sensor(entity_id):
                info["status"] = "Riferimento circolare"
            elif row is None:
                info["status"] = "Entità non trovata"
            elif not row.get("enabled", True):
                info["status"] = "Entità disabilitata"
            elif not valid_role_unit(row, role):
                info["status"] = "Unità non valida"
            else:
                try:
                    value = float(row.get("state"))
                    if not math.isfinite(value):
                        raise ValueError("non-finite value")
                    if role != "battery_soc_sensor" and row.get("unit") == "kW":
                        value *= 1000.0
                    if role == "grid_power_sensor" and config.get("grid_power_invert", False):
                        value = -value
                    if role == "battery_power_sensor" and config.get("battery_power_invert", False):
                        value = -value
                    info["value"] = round(value, 2)
                    info["status"] = "OK"
                    info["provider"] = provider_for(row)
                except (ValueError, TypeError, OverflowError):
                    info["status"] = "Non disponibile"
        if entity_id and info["status"] != "OK":
            warnings.append(f"{LABELS[role]}: {info['status']}")
        sources[role] = info

    balance = None
    grid = sources["grid_power_sensor"]
    pv = sources["pv_power_sensor"]
    battery = sources["battery_power_sensor"]
    if grid["status"] == "OK" and pv["status"] == "OK" and (
        not battery["entity_id"] or battery["status"] == "OK"
    ):
        for group in groups:
            candidate = group.get("sources", {})
            if candidate.get("grid_power_sensor") != grid["entity_id"]:
                continue
            if candidate.get("pv_power_sensor") != pv["entity_id"]:
                continue
            if battery["entity_id"] and candidate.get("battery_power_sensor") != battery["entity_id"]:
                continue
            house_id = candidate.get("power_sensor")
            house = registry.get(house_id)
            if not house or not valid_role_unit(house, "power_sensor"):
                continue
            try:
                measured = float(house.get("state"))
                if not math.isfinite(measured):
                    continue
                if house.get("unit") == "kW":
                    measured *= 1000.0
            except (TypeError, ValueError, OverflowError):
                continue
            estimated = max(0.0, pv["value"] + grid["value"] +
                            (battery["value"] if battery["value"] is not None else 0.0))
            error = abs(estimated - measured)
            tolerance = max(250.0, measured * 0.15)
            balance = {
                "reference_entity_id": house_id,
                "native_house_w": round(measured, 1),
                "calculated_house_w": round(estimated, 1),
                "difference_w": round(error, 1),
                "tolerance_w": round(tolerance, 1),
                "status": "Coerente" if error <= tolerance else "Da verificare",
            }
            if error > tolerance:
                warnings.append("Bilancio energetico incoerente: verificare polarità e tempi di campionamento")
            break

    configured = [info for info in sources.values() if info["entity_id"]]
    health = "Da configurare" if not configured else (
        "Da verificare" if warnings else "OK"
    )
    return {"health": health, "sources": sources, "balance": balance, "warnings": warnings}

def format_diagnostics(result: dict) -> dict[str, str]:
    lines = []
    for role in SOURCE_ROLES:
        source = result["sources"][role]
        value = source["value"]
        rendered = f"{value:g} {source['unit']}" if value is not None else source["status"]
        lines.append(f"{LABELS[role]}: {source['entity_id'] or 'non configurato'} = {rendered}")
    balance = result.get("balance")
    if balance:
        balance_text = (f"{balance['status']} | casa SENEC {balance['native_house_w']:g} W"
                        f" | calcolata {balance['calculated_house_w']:g} W"
                        f" | scarto {balance['difference_w']:g} W")
    else:
        balance_text = "Non confrontabile: occorrono casa, rete e FV dello stesso dispositivo"
    return {
        "health": result["health"],
        "sources": " ; ".join(lines),
        "balance": balance_text,
        "warnings": " ; ".join(result["warnings"]) or "Nessuna anomalia rilevata",
    }
