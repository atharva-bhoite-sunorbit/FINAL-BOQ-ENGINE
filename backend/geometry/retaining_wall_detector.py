from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_retaining_walls(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 3.5
    default_thickness = 0.30

    for entity in entities(cad_data):
        if not matches(entity, ("RETAINING_WALL", "RET_WALL", "BASEMENT_WALL")):
            continue

        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        hatch_area = float(entity.get("area", 0.0))
        thickness = float(entity.get("thickness", 0.0) or entity.get("width", 0.0) or default_thickness)

        if length <= 0 and hatch_area > 0 and thickness > 0:
            length = hatch_area / thickness
        if length <= 0 and hatch_area <= 0:
            continue

        height = float(entity.get("height", default_height) or default_height)
        volume = length * thickness * height
        element_id = f"RW_{len(results) + 1:04d}"

        geom = {
            "length": round(length, 4),
            "thickness": round(thickness, 4),
            "height": round(height, 4),
            "area": round(length * height, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="RETAINING_WALL",
            subtype="BASEMENT_WALL" if "BASEMENT" in entity.get("layer", "").upper() else "RCC_RETAINING_WALL",
            entity=entity,
            confidence=0.92,
            status="MEASURED" if entity.get("height") else "ASSUMED",
            material_hint="RCC_M30",
            geometry_override=geom,
        )
        results.append(elem)

    return results
