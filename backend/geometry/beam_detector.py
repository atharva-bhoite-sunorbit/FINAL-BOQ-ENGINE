from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_beams(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_width = 0.23
    default_depth = 0.45

    for entity in entities(cad_data):
        if not matches(entity, ("BEAM", "BM", "PLINTH_BEAM", "TIE_BEAM", "RCC_BEAM")):
            continue

        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        hatch_area = float(entity.get("area", 0.0))
        width = float(entity.get("width", 0.0) or default_width)
        depth = float(entity.get("height", 0.0) or entity.get("depth", 0.0) or default_depth)

        if length <= 0 and hatch_area > 0 and width > 0:
            length = hatch_area / width

        if length <= 0 and hatch_area <= 0:
            continue

        volume = length * width * depth
        subtype = _classify_beam(entity)
        element_id = f"BM_{len(results) + 1:04d}"
        
        status = "MEASURED" if (entity.get("width") and entity.get("height")) else "ASSUMED"
        geom = {
            "length": round(length, 4),
            "width": round(width, 4),
            "depth": round(depth, 4),
            "area": round(length * width, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="BEAM",
            subtype=subtype,
            entity=entity,
            confidence=0.92,
            status=status,
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_beam(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "PLINTH" in sig or "PB" in sig:
        return "PLINTH_BEAM"
    elif "TIE" in sig or "TB" in sig:
        return "TIE_BEAM"
    elif "STEEL" in sig or "ISMB" in sig:
        return "STEEL_BEAM"
    return "RCC_BEAM"
