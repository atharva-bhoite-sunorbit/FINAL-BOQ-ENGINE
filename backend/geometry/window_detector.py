from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_windows(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 1.20
    default_width = 1.50

    for entity in entities(cad_data):
        # Prevent double-counting sub-lines of expanded window block inserts
        if entity.get("source_insert_handle"):
            continue

        if not matches(entity, ("WINDOW", "WIN_", "W0", "W1", "W2", "W3", "VENT", "GLAZING")):
            continue

        width = float(entity.get("width", 0.0) or entity.get("length", 0.0) or default_width)
        if width > 6.0:
            width = default_width
        height = float(entity.get("height", default_height) or default_height)
        area = width * height
        subtype = _classify_window(entity)
        element_id = f"WIN_{len(results) + 1:04d}"

        geom = {
            "width": round(width, 4),
            "height": round(height, 4),
            "area": round(area, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="WINDOW",
            subtype=subtype,
            entity=entity,
            confidence=0.92,
            status="MEASURED" if entity.get("width") else "ASSUMED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_window(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "VENT" in sig:
        return "LOUVERED_WINDOW"
    elif "CASEMENT" in sig:
        return "CASEMENT_WINDOW"
    elif "FIXED" in sig:
        return "FIXED_WINDOW"
    return "SLIDING_WINDOW"
