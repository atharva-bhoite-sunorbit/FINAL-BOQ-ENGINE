from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_electrical(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("ELEC", "LIGHT", "POWER", "SWITCH", "SOCKET", "CONDUIT", "CABLE_TRAY", "DB")):
            continue

        subtype = _classify_electrical(entity)
        element_id = f"ELE_{len(results) + 1:04d}"
        
        # Conduit or Cable tray might have length
        length = float(entity.get("length", 0.0) or 0.0)
        geom = {"length": round(length, 4)} if length > 0 else {"quantity": 1.0}

        elem = build_element(
            element_id=element_id,
            element_type="ELECTRICAL",
            subtype=subtype,
            entity=entity,
            confidence=0.90,
            status="MEASURED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_electrical(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "LIGHT" in sig:
        return "LIGHT_POINT"
    elif "POWER" in sig or "SOCKET" in sig:
        return "POWER_POINT"
    elif "SWITCH" in sig:
        return "SWITCHBOARD"
    elif "DB" in sig or "PANEL" in sig:
        return "DISTRIBUTION_BOARD"
    elif "TRAY" in sig:
        return "CABLE_TRAY"
    elif "CONDUIT" in sig:
        return "CONDUIT"
    return "ELECTRICAL_POINT"
