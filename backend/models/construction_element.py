from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ConstructionElement:
    element_id: str
    element_type: str
    subtype: str
    geometry: dict[str, float] = field(default_factory=dict)
    material_hint: Optional[str] = None
    floor: Optional[str] = "GROUND"
    room: Optional[str] = None
    source_entities: list[str] = field(default_factory=list)
    source_layers: list[str] = field(default_factory=list)
    source_dimensions: list[str] = field(default_factory=list)
    source_annotations: list[str] = field(default_factory=list)
    confidence: float = 0.90
    status: str = "MEASURED"  # MEASURED | DERIVED | INFERRED | ASSUMED | NOT_AVAILABLE
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "element_type": self.element_type,
            "subtype": self.subtype,
            "geometry": {k: round(v, 4) if isinstance(v, float) else v for k, v in self.geometry.items()},
            "material_hint": self.material_hint,
            "floor": self.floor,
            "room": self.room,
            "source_entities": self.source_entities,
            "source_layers": self.source_layers,
            "source_dimensions": self.source_dimensions,
            "source_annotations": self.source_annotations,
            "confidence": round(self.confidence, 2),
            "status": self.status,
            **self.extra,
        }
