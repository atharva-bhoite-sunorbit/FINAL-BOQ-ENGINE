from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_floors(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("FLOOR", "FLR", "TILES", "VITRIFIED", "MARBLE", "GRANITE", "SCREED", "FLOORING")):
            continue
        if matches(entity, ("FLOOR_PLAN", "FLR_LVL", "LEVEL")):
            continue

        area = float(entity.get("area", 0.0))
        perimeter = float(entity.get("perimeter", 0.0) or (entity.get("length", 0.0) * 2 if entity.get("length") else 0.0))

        if area <= 0 and perimeter > 0:
            area = (perimeter / 4.0) ** 2
        if area <= 0:
            continue

        subtype = _classify_flooring(entity)
        element_id = f"FLR_{len(results) + 1:04d}"
        geom = {
            "area": round(area, 4),
            "perimeter": round(perimeter, 4),
            "skirting_length": round(perimeter, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="FLOOR",
            subtype=subtype,
            entity=entity,
            confidence=0.93,
            status="MEASURED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_flooring(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "MARBLE" in sig:
        return "MARBLE"
    elif "GRANITE" in sig:
        return "GRANITE"
    elif "CERAMIC" in sig:
        return "CERAMIC_TILES"
    elif "WOOD" in sig or "WOODEN" in sig:
        return "WOODEN"
    elif "VDF" in sig or "TRIMIX" in sig:
        return "VDF"
    return "VITRIFIED_TILES"
