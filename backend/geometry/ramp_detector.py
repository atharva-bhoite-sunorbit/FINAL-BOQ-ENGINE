from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_ramps(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_thickness = 0.20

    for entity in entities(cad_data):
        if not matches(entity, ("RAMP", "VEHICULAR_RAMP")):
            continue

        area = float(entity.get("area", 0.0))
        length = float(entity.get("length", 0.0))
        width = float(entity.get("width", 2.0))

        if area <= 0 and length > 0:
            area = length * width
        if area <= 0:
            continue

        volume = area * default_thickness
        element_id = f"RMP_{len(results) + 1:04d}"
        geom = {
            "area": round(area, 4),
            "length": round(length, 4),
            "width": round(width, 4),
            "thickness": default_thickness,
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="RAMP",
            subtype="VEHICULAR_RAMP" if "VEH" in entity.get("layer", "").upper() else "ACCESSIBLE_RAMP",
            entity=entity,
            confidence=0.90,
            status="DERIVED",
            material_hint="RCC_M25",
            geometry_override=geom,
        )
        results.append(elem)

    return results
