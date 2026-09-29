from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_grids(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("GRID", "STR_GRID", "COL_GRID", "GRID_LINE")):
            continue

        length = float(entity.get("length", 0.0) or 0.0)
        if length <= 0:
            continue

        element_id = f"GRD_{len(results) + 1:04d}"
        geom = {
            "length": round(length, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="GRID",
            subtype="STRUCTURAL_GRID_LINE",
            entity=entity,
            confidence=0.95,
            status="MEASURED",
            material_hint="REFERENCE",
            geometry_override=geom,
        )
        results.append(elem)

    return results
