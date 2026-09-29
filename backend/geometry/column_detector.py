from __future__ import annotations

import math
from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_columns(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 3.0

    for entity in entities(cad_data):
        if not matches(entity, ("COLUMN", "COL", "PILLAR", "RCC_COL", "STR_COL")):
            continue
        
        # Determine cross section
        area = float(entity.get("area", 0.0))
        perimeter = float(entity.get("perimeter", 0.0))
        width = float(entity.get("width", 0.0))
        length = float(entity.get("length", 0.0))
        radius = float(entity.get("radius", 0.0))

        if radius > 0:
            area = math.pi * radius * radius
            perimeter = 2 * math.pi * radius
            width = radius * 2
            length = radius * 2
        elif width > 0 and length > 0:
            if area <= 0:
                area = width * length
            if perimeter <= 0:
                perimeter = 2 * (width + length)
        elif area > 0:
            # Assume roughly square if dimensions not directly given
            side = math.sqrt(area)
            width = length = side
            if perimeter <= 0:
                perimeter = 4 * side
        else:
            # Check if standard 0.3m x 0.45m column
            width = 0.30
            length = 0.45
            area = width * length
            perimeter = 2 * (width + length)

        height = float(entity.get("height", default_height) or default_height)
        status = "MEASURED" if entity.get("height") else "ASSUMED"
        volume = area * height

        subtype = _classify_column(entity)
        element_id = f"COL_{len(results) + 1:04d}"
        geom = {
            "width": round(width, 4),
            "length": round(length, 4),
            "height": round(height, 4),
            "area": round(area, 4),
            "perimeter": round(perimeter, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="COLUMN",
            subtype=subtype,
            entity=entity,
            confidence=0.94,
            status=status,
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_column(entity: dict[str, Any]) -> str:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    if "STEEL" in sig or "ISMB" in sig or "UC" in sig:
        return "STEEL_COLUMN"
    elif "COMPOSITE" in sig:
        return "COMPOSITE_COLUMN"
    return "RCC_COLUMN"
