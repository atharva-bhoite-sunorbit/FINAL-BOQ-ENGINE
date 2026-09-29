from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_sanitary(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if entity.get("source_insert_handle"):
            continue

        if not matches(entity, ("SANITARY", "WC", "COMMODE", "WASH_BASIN", "BASIN", "URINAL", "SINK", "SHOWER", "TOILET_FIXTURE")):
            continue

        subtype = _classify_sanitary(entity)
        element_id = f"SAN_{len(results) + 1:04d}"
        geom = {"quantity": 1.0}

        elem = build_element(
            element_id=element_id,
            element_type="SANITARY",
            subtype=subtype,
            entity=entity,
            confidence=0.92,
            status="MEASURED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_sanitary(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "WC" in sig or "COMMODE" in sig or "EWC" in sig:
        return "WC"
    elif "BASIN" in sig or "WB" in sig:
        return "WASH_BASIN"
    elif "URINAL" in sig:
        return "URINAL"
    elif "SHOWER" in sig:
        return "SHOWER"
    elif "SINK" in sig:
        return "SINK"
    return "SANITARY_FIXTURE"
