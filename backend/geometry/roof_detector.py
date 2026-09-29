from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_roofs(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("ROOF", "TERRACE", "TIN_SHED", "TRUSS_ROOF")):
            continue

        area = float(entity.get("area", 0.0))
        perimeter = float(entity.get("perimeter", 0.0))

        if area <= 0 and perimeter > 0:
            area = (perimeter / 4.0) ** 2
        if area <= 0:
            continue

        element_id = f"ROF_{len(results) + 1:04d}"
        geom = {
            "area": round(area, 4),
            "perimeter": round(perimeter, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="ROOF",
            subtype="METAL_ROOF" if "SHEET" in entity.get("layer", "").upper() else "RCC_ROOF",
            entity=entity,
            confidence=0.91,
            status="DERIVED",
            material_hint="RCC_ROOF",
            geometry_override=geom,
        )
        results.append(elem)

    return results
