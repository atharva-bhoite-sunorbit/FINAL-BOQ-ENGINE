from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_handrails(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("HANDRAIL", "WALL_HANDRAIL")):
            continue

        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        if length <= 0:
            continue

        element_id = f"HDR_{len(results) + 1:04d}"
        geom = {
            "length": round(length, 4),
            "running_meter": round(length, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="HANDRAIL",
            subtype="WALL_MOUNTED_HANDRAIL",
            entity=entity,
            confidence=0.91,
            status="MEASURED",
            material_hint="SS_HANDRAIL",
            geometry_override=geom,
        )
        results.append(elem)

    return results
