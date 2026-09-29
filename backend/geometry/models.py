from __future__ import annotations

from typing import Any


def construction_element(
    element_id: str,
    element_type: str,
    subtype: str,
    geometry: dict[str, Any],
    source_entities: list[str],
    source_layers: list[str],
    confidence: float,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "element_id": element_id,
        "element_type": element_type,
        "subtype": subtype,
        "geometry": geometry,
        "source_entities": source_entities,
        "source_layers": source_layers,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        **extra,
    }
