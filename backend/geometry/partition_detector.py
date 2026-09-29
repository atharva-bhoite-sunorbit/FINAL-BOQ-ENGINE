from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from .common import build_element, entities, matches


def detect_partitions(cad_data: dict[str, Any]) -> list[ConstructionElement]:
    results: list[ConstructionElement] = []
    default_height = 3.0
    import re

    for entity in entities(cad_data):
        if entity.get("source_insert_handle"):
            blk = str(entity.get("block_name", "")).upper()
            if not any(k in blk for k in ("PARTITION", "GYPSUM", "DRYWALL", "GLASS_PARTITION", "ALUM_PARTITION")):
                continue

        if entity.get("entity_type") not in {"LINE", "LWPOLYLINE", "POLYLINE", "HATCH", "INSERT"}:
            continue
        
        if not matches(entity, ("PARTITION", "GYPSUM", "DRYWALL", "GLASS_PARTITION", "ALUM_PARTITION", "INT_WALL")):
            continue

        subtype, thickness = _classify_partition(entity)
        length = float(entity.get("length", 0.0) or (entity.get("perimeter", 0.0) / 2.0 if entity.get("perimeter") else 0.0))
        hatch_area = float(entity.get("area", 0.0))
        
        if length <= 0 and hatch_area > 0 and thickness > 0:
            length = hatch_area / thickness

        if length <= 0 and hatch_area <= 0:
            continue

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

        element_id = f"PAR_{len(results) + 1:04d}"
        geom = {
            "length": round(length, 4),
            "thickness": round(thickness, 4),
            "height": round(height, 4),
            "area": round(face_area, 4),
            "volume": round(volume, 4),
        }

        elem = build_element(
            element_id=element_id,
            element_type="PARTITION",
            subtype=subtype,
            entity=entity,
            confidence=0.91,
            status=status,
            material_hint=subtype,
            geometry_override=geom,
        )
        results.append(elem)

    return results


def _classify_partition(entity: dict[str, Any]) -> tuple[str, float]:
    sig = f"{entity.get('layer', '')} {entity.get('block_name', '')} {entity.get('text', '')}".upper()
    
    if "GLASS" in sig:
        thickness = 0.012 if "12MM" in sig else (0.010 if "10MM" in sig else 0.012)
        return "GLASS_PARTITION", thickness
    elif "ALUM" in sig:
        return "ALUMINIUM_PARTITION", 0.075
    elif "DRYWALL" in sig:
        thickness = 0.10 if "100" in sig else 0.075
        return "DRYWALL", thickness
    
    # Default Gypsum Partition
    thickness = 0.10 if "100" in sig else (0.075 if "75" in sig else 0.075)
    return "GYPSUM_PARTITION", thickness
