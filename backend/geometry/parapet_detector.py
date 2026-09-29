from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_parapets(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 1.00
    default_thickness = 0.15

    for entity in entities(cad_data):
        if not matches(entity, ("PARAPET", "PARAPET_WALL")):
            continue

        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        if length <= 0:
            continue

        height = float(entity.get("height", default_height) or default_height)
        volume = length * default_thickness * height
        element_id = f"PRP_{len(results) + 1:04d}"

        geom = {
            "length": round(length, 4),
            "height": round(height, 4),
            "thickness": default_thickness,
            "area": round(length * height, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="PARAPET",
            subtype="RCC_PARAPET" if "RCC" in entity.get("layer", "").upper() else "MASONRY_PARAPET",
            entity=entity,
            confidence=0.92,
            status="DERIVED",
            material_hint="MASONRY_PARAPET",
            geometry_override=geom,
        )
        results.append(elem)

    return results
