from __future__ import annotations

import math
from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_footings(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_thickness = 0.45

    for entity in entities(cad_data):
        if not matches(entity, ("FOOTING", "FTG", "ISOLATED_FTG", "COMBINED_FTG")):
            continue

        width = float(entity.get("width", 0.0))
        length = float(entity.get("length", 0.0))
        area = float(entity.get("area", 0.0))
        thickness = float(entity.get("height", 0.0) or entity.get("thickness", 0.0) or default_thickness)

        if width > 0 and length > 0:
            if area <= 0:
                area = width * length
        elif area > 0:
            side = math.sqrt(area)
            width = length = side
        else:
            width = length = 1.5
            area = 2.25

        volume = area * thickness
        element_id = f"FTG_{len(results) + 1:04d}"
        geom = {
            "width": round(width, 4),
            "length": round(length, 4),
            "thickness": round(thickness, 4),
            "area": round(area, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="FOOTING",
            subtype="COMBINED_FOOTING" if "COMBINED" in entity.get("layer", "").upper() else "ISOLATED_FOOTING",
            entity=entity,
            confidence=0.92,
            status="DERIVED",
            material_hint="RCC_M25",
            geometry_override=geom,
        )
        results.append(elem)

    return results
