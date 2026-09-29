from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_railings(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 1.05

    for entity in entities(cad_data):
        if not matches(entity, ("RAILING", "BALUSTRADE", "BALCONY_RAILING", "STAIR_RAILING")):
            continue

        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        if length <= 0:
            continue

        subtype = _classify_railing(entity)
        element_id = f"RLG_{len(results) + 1:04d}"
        geom = {
            "length": round(length, 4),
            "height": default_height,
            "running_meter": round(length, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="RAILING",
            subtype=subtype,
            entity=entity,
            confidence=0.92,
            status="MEASURED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_railing(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "GLASS" in sig:
        return "GLASS_RAILING"
    elif "MS" in sig or "MILD_STEEL" in sig:
        return "MS_RAILING"
    return "SS_RAILING"
