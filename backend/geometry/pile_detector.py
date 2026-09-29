from __future__ import annotations

import math
from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_piles(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_diameter = 0.50
    default_length = 12.0

    for entity in entities(cad_data):
        if not matches(entity, ("PILE", "PILES", "BORED_PILE")):
            continue
        if matches(entity, ("PILE_CAP", "CAP")):
            continue

        radius = float(entity.get("radius", 0.0))
        diameter = radius * 2 if radius > 0 else float(entity.get("diameter", 0.0) or default_diameter)
        length = float(entity.get("height", 0.0) or entity.get("length", 0.0) or default_length)
        area = math.pi * ((diameter / 2.0) ** 2)
        volume = area * length

        element_id = f"PIL_{len(results) + 1:04d}"
        geom = {
            "diameter": round(diameter, 4),
            "length": round(length, 4),
            "area": round(area, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="PILE",
            subtype="BORED_CAST_IN_SITU_PILE",
            entity=entity,
            confidence=0.91,
            status="DERIVED",
            material_hint="RCC_M30",
            geometry_override=geom,
        )
        results.append(elem)

    return results
