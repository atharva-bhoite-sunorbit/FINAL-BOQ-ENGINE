from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_plumbing(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("PLUMB", "PIPE", "DRAIN", "SEWER", "WATER_SUPPLY", "VALVE", "WATER_TANK")):
            continue

        subtype = _classify_plumbing(entity)
        element_id = f"PLB_{len(results) + 1:04d}"
        
        length = float(entity.get("length", 0.0) or 0.0)
        geom = {"length": round(length, 4)} if length > 0 else {"quantity": 1.0}

        elem = build_element(
            element_id=element_id,
            element_type="PLUMBING",
            subtype=subtype,
            entity=entity,
            confidence=0.90,
            status="MEASURED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_plumbing(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "DRAIN" in sig or "SEWER" in sig or "SOIL" in sig:
        return "DRAINAGE_PIPE"
    elif "VALVE" in sig:
        return "VALVE"
    elif "TANK" in sig:
        return "WATER_TANK"
    return "WATER_SUPPLY_PIPE"
