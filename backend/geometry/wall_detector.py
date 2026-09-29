from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_walls(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 3.0
    import re
    
    for entity in entities(cad_data):
        # Skip sub-entities of expanded non-wall blocks (e.g. doors, fixtures)
        if entity.get("source_insert_handle"):
            blk = str(entity.get("block_name", "")).upper()
            if not any(k in blk for k in ("WALL", "MASONRY", "BRICK", "AAC", "BLOCK", "CWALL")):
                continue

        if entity.get("entity_type") not in {"LINE", "LWPOLYLINE", "POLYLINE", "HATCH", "INSERT"}:
            continue
        
        if not matches(entity, ("WALL", "MASONRY", "BRICK", "AAC", "BLOCK", "CWALL")):
            continue
        if matches(entity, ("PARTITION", "GLASS", "DRYWALL", "GYPSUM")):
            continue

        subtype, thickness = _classify_wall(entity)
        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        hatch_area = float(entity.get("area", 0.0))
        
        # If length is 0 but hatch area exists, derive length from area/thickness
        if length <= 0 and hatch_area > 0 and thickness > 0:
            length = hatch_area / thickness
        
        if length <= 0 and hatch_area <= 0:
            continue

        # Check for explicit height in layer name or text (e.g., 'UPTO 2400 MM', 'H=3000')
        height = float(entity.get("height", 0.0) or 0.0)
        status = "ASSUMED"
        if height > 0:
            status = "MEASURED"
        else:
            sig = f"{entity.get('layer', '')} {entity.get('text', '')}".upper()
            m_h = re.search(r"(?:UPTO|HEIGHT|H\s*=|HIGH)\s*(\d{3,4})\s*(?:MM)?", sig)
            if m_h:
                parsed_h = float(m_h.group(1)) / 1000.0
                if 0.5 <= parsed_h <= 10.0:
                    height = parsed_h
                    status = "MEASURED"
            if height <= 0:
                height = default_height
        
        face_area = length * height
        volume = length * thickness * height

        element_id = f"WAL_{len(results) + 1:04d}"
        geom = {
            "length": round(length, 4),
            "thickness": round(thickness, 4),
            "height": round(height, 4),
            "area": round(face_area, 4),
            "volume": round(volume, 4),
        }
        
        elem = build_element(
            element_id=element_id,
            element_type="WALL",
            subtype=subtype,
            entity=entity,
            confidence=0.92,
            status=status,
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_wall(entity: dict[str, Any]) -> tuple[str, float]:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    
    if "AAC" in sig or "SIPOREX" in sig:
        thickness = 0.20 if "200" in sig else (0.10 if "100" in sig else 0.15)
        return "AAC_BLOCK_WALL", thickness
    elif "BRICK" in sig:
        thickness = 0.23 if ("230" in sig or "9IN" in sig) else (0.115 if "115" in sig else 0.15)
        return "BRICK_WALL", thickness
    elif "RCC" in sig or "CONCRETE" in sig:
        thickness = 0.20 if "200" in sig else 0.15
        return "RCC_WALL", thickness
    elif "BLOCK" in sig:
        thickness = 0.20 if "200" in sig else 0.15
        return "CONCRETE_BLOCK_WALL", thickness
    
    t = float(entity.get("thickness", 0.0) or entity.get("width", 0.0) or 0.15)
    if t <= 0.02:
        t = 0.15
    return "AAC_BLOCK_WALL", t
