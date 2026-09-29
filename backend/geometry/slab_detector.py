from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_slabs(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_thickness = 0.15

    for entity in entities(cad_data):
        if not matches(entity, ("SLAB", "RCC_SLAB", "FLOOR_SLAB", "ROOF_SLAB", "SUNK_SLAB")):
            continue

        area = float(entity.get("area", 0.0))
        perimeter = float(entity.get("perimeter", 0.0) or (entity.get("length", 0.0) * 2 if entity.get("length") else 0.0))
        thickness = float(entity.get("thickness", 0.0) or entity.get("height", 0.0) or default_thickness)

        if area <= 0 and perimeter > 0:
            area = (perimeter / 4.0) ** 2

        if area <= 0:
            continue

        volume = area * thickness
        subtype = _classify_slab(entity)
        element_id = f"SLB_{len(results) + 1:04d}"
        status = "MEASURED" if entity.get("area") else "DERIVED"

        geom = {
            "area": round(area, 4),
            "thickness": round(thickness, 4),
            "perimeter": round(perimeter, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="SLAB",
            subtype=subtype,
            entity=entity,
            confidence=0.93,
            status=status,
            material_hint="RCC_M25",
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_slab(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "SUNK" in sig:
        return "SUNK_SLAB"
    elif "ONE_WAY" in sig or "1WAY" in sig:
        return "ONE_WAY_SLAB"
    elif "TWO_WAY" in sig or "2WAY" in sig:
        return "TWO_WAY_SLAB"
    elif "FLAT" in sig:
        return "FLAT_SLAB"
    return "RCC_SLAB"
