from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_openings(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("OPENING", "SHAFT", "VOID", "CUTOUT", "OTS", "DUCT_OPENING")):
            continue

        width = float(entity.get("width", 0.0) or entity.get("length", 0.0) or 0.0)
        height = float(entity.get("height", 0.0) or 0.0)
        area = float(entity.get("area", 0.0))

        if area <= 0 and width > 0 and height > 0:
            area = width * height
        elif area > 0 and width <= 0:
            width = area ** 0.5
            height = width

        if area <= 0:
            continue

        subtype = _classify_opening(entity)
        element_id = f"OPN_{len(results) + 1:04d}"

        geom = {
            "width": round(width, 4),
            "height": round(height, 4),
            "area": round(area, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="OPENING",
            subtype=subtype,
            entity=entity,
            confidence=0.91,
            status="MEASURED",
            material_hint="OPENING",
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_opening(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "SHAFT" in sig or "DUCT" in sig:
        return "SHAFT_OPENING"
    elif "CUTOUT" in sig or "VOID" in sig:
        return "CUTOUT"
    return "WALL_OPENING"
