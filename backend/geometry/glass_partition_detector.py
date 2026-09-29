from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_glass_partitions(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 2.40

    for entity in entities(cad_data):
        if not matches(entity, ("GL_PART", "GLASS_PARTITION", "FRAMELESS_GLASS", "TOUGHENED_GLASS")):
            continue

        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        hatch_area = float(entity.get("area", 0.0))
        if length <= 0 and hatch_area > 0:
            length = hatch_area / 0.012
        if length <= 0:
            continue

        height = float(entity.get("height", default_height) or default_height)
        area = length * height
        element_id = f"GLP_{len(results) + 1:04d}"

        geom = {
            "length": round(length, 4),
            "height": round(height, 4),
            "thickness": 0.012,
            "area": round(area, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="GLASS_PARTITION",
            subtype="FRAMELESS_GLASS" if "FRAMELESS" in entity.get("layer", "").upper() else "ALUMINIUM_FRAMED_GLASS",
            entity=entity,
            confidence=0.94,
            status="MEASURED" if entity.get("height") else "ASSUMED",
            material_hint="TOUGHENED_GLASS",
            geometry_override=geom,
        )
        results.append(elem)

    return results
