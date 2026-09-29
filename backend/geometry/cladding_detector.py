from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_claddings(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []

    for entity in entities(cad_data):
        if not matches(entity, ("CLADDING", "ACP", "STONE_CLADDING", "HPL")):
            continue

        area = float(entity.get("area", 0.0))
        length = float(entity.get("length", 0.0))
        height = float(entity.get("height", 3.0))

        if area <= 0 and length > 0:
            area = length * height
        if area <= 0:
            continue

        subtype = _classify_cladding(entity)
        element_id = f"CLD_{len(results) + 1:04d}"
        geom = {
            "area": round(area, 4),
            "length": round(length, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="CLADDING",
            subtype=subtype,
            entity=entity,
            confidence=0.91,
            status="DERIVED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_cladding(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "STONE" in sig:
        return "STONE_CLADDING"
    elif "HPL" in sig:
        return "HPL_CLADDING"
    return "ACP_CLADDING"
