from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_staircases(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_waist_slab = 0.15

    for entity in entities(cad_data):
        if not matches(entity, ("STAIR", "STAIRCASE", "STEPS", "RISER", "TREAD")):
            continue

        area = float(entity.get("area", 0.0))
        length = float(entity.get("length", 0.0))
        width = float(entity.get("width", 1.2))

        if area <= 0 and length > 0:
            area = length * width

        if area <= 0:
            continue

        # Approximate concrete volume for waist slab + steps (~0.25m equivalent uniform slab)
        volume = area * 0.25
        element_id = f"STR_{len(results) + 1:04d}"
        geom = {
            "area": round(area, 4),
            "width": round(width, 4),
            "waist_slab": default_waist_slab,
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="STAIRCASE",
            subtype="RCC_DOG_LEGGED" if "DOG" in entity.get("layer", "").upper() else "RCC_STAIRCASE",
            entity=entity,
            confidence=0.91,
            status="DERIVED",
            material_hint="RCC_M25",
            geometry_override=geom,
        )
        results.append(elem)

    return results
