from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_lintels(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_depth = 0.15
    default_width = 0.20

    for entity in entities(cad_data):
        if not matches(entity, ("LINTEL", "LINTEL_BEAM", "LNTL")):
            continue

        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        width = float(entity.get("width", 0.0) or default_width)
        depth = float(entity.get("height", 0.0) or entity.get("depth", 0.0) or default_depth)

        if length <= 0:
            continue

        volume = length * width * depth
        element_id = f"LNT_{len(results) + 1:04d}"
        geom = {
            "length": round(length, 4),
            "width": round(width, 4),
            "depth": round(depth, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="LINTEL",
            subtype="RCC_LINTEL",
            entity=entity,
            confidence=0.90,
            status="DERIVED",
            material_hint="RCC_M25",
            geometry_override=geom,
        )
        results.append(elem)

    return results
