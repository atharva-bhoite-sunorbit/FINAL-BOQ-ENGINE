from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_rooms(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 3.0

    for entity in entities(cad_data):
        if not matches(entity, ("ROOM", "SPACE", "AREA", "BEDROOM", "LIVING", "KITCHEN", "TOILET", "BATH", "BALCONY", "LOBBY", "CORRIDOR", "OFFICE")):
            continue

        area = float(entity.get("area", 0.0))
        perimeter = float(entity.get("perimeter", 0.0) or (entity.get("length", 0.0) * 2 if entity.get("length") else 0.0))

        if area <= 0 and perimeter > 0:
            area = (perimeter / 4.0) ** 2
        if area <= 0:
            continue

        subtype = _classify_room(entity)
        element_id = f"RM_{len(results) + 1:04d}"
        height = float(entity.get("height", default_height) or default_height)
        volume = area * height

        geom = {
            "area": round(area, 4),
            "perimeter": round(perimeter, 4),
            "height": round(height, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="ROOM",
            subtype=subtype,
            entity=entity,
            confidence=0.92,
            status="MEASURED",
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_room(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    for name in ("TOILET", "BATH", "KITCHEN", "BEDROOM", "LIVING", "BALCONY", "CORRIDOR", "LOBBY", "OFFICE"):
        if name in sig:
            return name
    return "ROOM"
