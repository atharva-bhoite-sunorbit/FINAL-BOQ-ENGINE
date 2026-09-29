from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_hvac(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("HVAC", "DUCT", "DIFFUSER", "GRILLE", "FCU", "AHU", "AC_UNIT", "CHILLER")):
            continue

        subtype = _classify_hvac(entity)
        element_id = f"HVC_{len(results) + 1:04d}"
        
        area = float(entity.get("area", 0.0))
        length = float(entity.get("length", 0.0) or 0.0)
        geom = {"area": round(area, 4)} if area > 0 else ({"length": round(length, 4)} if length > 0 else {"quantity": 1.0})

        elem = build_element(
            element_id=element_id,
            element_type="HVAC",
            subtype=subtype,
            entity=entity,
            confidence=0.91,
            status="MEASURED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_hvac(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "DIFFUSER" in sig or "GRILLE" in sig:
        return "DIFFUSER"
    elif "FCU" in sig:
        return "FCU"
    elif "AHU" in sig:
        return "AHU"
    elif "CHILLER" in sig or "ODU" in sig:
        return "OUTDOOR_UNIT"
    return "DUCT"
