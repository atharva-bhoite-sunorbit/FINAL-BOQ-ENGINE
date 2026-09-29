from __future__ import annotations

import re
from typing import Any, Iterable, Optional
from backend.models.construction_element import ConstructionElement


def entities(cad_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [entity for entity in cad_data.get("entities", []) if isinstance(entity, dict)]


def texts(cad_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [text for text in cad_data.get("texts", []) if isinstance(text, dict)]


def blocks(cad_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [block for block in cad_data.get("blocks", []) if isinstance(block, dict)]


def signal(entity: dict[str, Any]) -> str:
    attributes = " ".join(str(item.get("text", "")) for item in entity.get("attributes", []))
    layer = str(entity.get("layer", ""))
    block_name = str(entity.get("block_name", ""))
    text = str(entity.get("text", ""))
    entity_type = str(entity.get("entity_type", ""))
    return f"{layer} {block_name} {text} {entity_type} {attributes}".upper()


def matches(entity: dict[str, Any], tokens: Iterable[str]) -> bool:
    sig = signal(entity)
    for token in tokens:
        if token.upper() in sig:
            return True
    return False


def source(entity: dict[str, Any]) -> tuple[list[str], list[str]]:
    handle = entity.get("handle")
    layer = entity.get("layer")
    return ([str(handle)] if handle else [], [str(layer)] if layer else [])


def dimension_geometry(entity: dict[str, Any], default_height: float = 3.0, default_thickness: float = 0.15) -> dict[str, float]:
    geom: dict[str, float] = {}
    for key in ("length", "width", "height", "thickness", "area", "perimeter", "volume", "radius", "diameter"):
        val = entity.get(key)
        if val is not None and isinstance(val, (int, float)) and val > 0:
            geom[key] = float(val)

    if "length" not in geom and "perimeter" in geom:
        geom["length"] = geom["perimeter"]
    if "area" not in geom and "length" in geom and "width" in geom:
        geom["area"] = geom["length"] * geom["width"]
    return geom


def build_element(
    element_id: str,
    element_type: str,
    subtype: str,
    entity: dict[str, Any],
    confidence: float = 0.90,
    status: str = "MEASURED",
    material_hint: Optional[str] = None,
    geometry_override: Optional[dict[str, float]] = None,
    extra: Optional[dict[str, Any]] = None,
) -> ConstructionElement:
    handles, layers = source(entity)
    geom = geometry_override or dimension_geometry(entity)
    return ConstructionElement(
        element_id=element_id,
        element_type=element_type,
        subtype=subtype,
        geometry=geom,
        material_hint=material_hint,
        floor=entity.get("floor", "GROUND"),
        room=entity.get("room"),
        source_entities=handles,
        source_layers=layers,
        source_dimensions=[str(entity.get("dimension"))] if entity.get("dimension") else [],
        source_annotations=[str(entity.get("text"))] if entity.get("text") else [],
        confidence=confidence,
        status=status,
        extra=extra or {},
    )
