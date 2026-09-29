from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_pile_caps(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_depth = 0.90

    for entity in entities(cad_data):
        if not matches(entity, ("PILE_CAP", "PILECAP", "PCAP")):
            continue

        area = float(entity.get("area", 0.0))
        depth = float(entity.get("height", 0.0) or entity.get("depth", 0.0) or default_depth)
        perimeter = float(entity.get("perimeter", 0.0))

        if area <= 0 and perimeter > 0:
            area = (perimeter / 4.0) ** 2
        if area <= 0:
            continue

        volume = area * depth
        element_id = f"PCAP_{len(results) + 1:04d}"
        geom = {
            "area": round(area, 4),
            "depth": round(depth, 4),
            "perimeter": round(perimeter, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="PILE_CAP",
            subtype="PILE_CAP",
            entity=entity,
            confidence=0.92,
            status="DERIVED",
            material_hint="RCC_M30",
            geometry_override=geom,
        )
        results.append(elem)

    return results
