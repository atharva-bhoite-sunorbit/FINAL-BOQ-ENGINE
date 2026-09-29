from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_ceilings(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("CEILING", "CLG", "FALSE_CEILING", "RCP", "GRID_CEILING", "POP")):
            continue

        area = float(entity.get("area", 0.0))
        perimeter = float(entity.get("perimeter", 0.0))

        if area <= 0 and perimeter > 0:
            area = (perimeter / 4.0) ** 2
        if area <= 0:
            continue

        subtype = _classify_ceiling(entity)
        element_id = f"CLG_{len(results) + 1:04d}"
        geom = {
            "area": round(area, 4),
            "perimeter": round(perimeter, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="CEILING",
            subtype=subtype,
            entity=entity,
            confidence=0.92,
            status="MEASURED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_ceiling(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "GRID" in sig or "ARMSTRONG" in sig or "2X2" in sig:
        return "GRID_CEILING"
    elif "POP" in sig:
        return "POP_CEILING"
    return "GYPSUM_FALSE_CEILING"
