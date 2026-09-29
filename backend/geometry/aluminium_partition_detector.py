from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_aluminium_partitions(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 2.40

    for entity in entities(cad_data):
        if not matches(entity, ("ALUM_PART", "ALUMINIUM_PARTITION", "AL_PART")):
            continue

        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        if length <= 0:
            continue

        height = float(entity.get("height", default_height) or default_height)
        area = length * height
        element_id = f"ALP_{len(results) + 1:04d}"

        geom = {
            "length": round(length, 4),
            "height": round(height, 4),
            "thickness": 0.075,
            "area": round(area, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="ALUMINIUM_PARTITION",
            subtype="POWDER_COATED_ALUM",
            entity=entity,
            confidence=0.92,
            status="MEASURED" if entity.get("height") else "ASSUMED",
            material_hint="ALUMINIUM",
            geometry_override=geom,
        )
        results.append(elem)

    return results
