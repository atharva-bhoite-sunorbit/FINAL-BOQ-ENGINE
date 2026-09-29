from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_doors(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 2.10
    default_width = 1.00

    for entity in entities(cad_data):
        # Prevent double-counting sub-lines of expanded door block inserts
        if entity.get("source_insert_handle"):
            continue

        if not matches(entity, ("DOOR", "DR_", "D0", "D1", "D2", "D3", "FLUSH_DOOR", "FIRE_DOOR")):
            continue

        width = float(entity.get("width", 0.0) or entity.get("length", 0.0) or default_width)
        if width > 3.0:  # If unusually wide, check if it's in mm or bounding box
            width = default_width
        height = float(entity.get("height", default_height) or default_height)
        area = width * height
        subtype = _classify_door(entity)
        element_id = f"DOR_{len(results) + 1:04d}"

        geom = {
            "width": round(width, 4),
            "height": round(height, 4),
            "area": round(area, 4),
            "thickness": 0.04,
        }

        elem = build_element(
            element_id=element_id,
            element_type="DOOR",
            subtype=subtype,
            entity=entity,
            confidence=0.93,
            status="MEASURED" if entity.get("width") else "ASSUMED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_door(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "FIRE" in sig or "FRD" in sig:
        return "FIRE_RATED_DOOR"
    elif "GLASS" in sig:
        return "GLASS_DOOR"
    elif "SLIDING" in sig:
        return "SLIDING_DOOR"
    elif "PANEL" in sig:
        return "PANELLED_DOOR"
    return "FLUSH_DOOR"
