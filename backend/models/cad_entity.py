from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CADEntity:
    entity_id: str
    entity_type: str
    layer: str = "0"
    block_name: Optional[str] = None
    closed: bool = False
    coordinates: list[list[float]] = field(default_factory=list)
    transformation: Optional[list[list[float]]] = None
    length: float = 0.0
    area: float = 0.0
    bounding_box: dict[str, float] = field(default_factory=dict)
    text: Optional[str] = None
    dimension_value: Optional[float] = None
    rotation: float = 0.0
    scale: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    color: Optional[int] = None
    linetype: Optional[str] = None
    handle: Optional[str] = None
    source_file: Optional[str] = None
    status: str = "CLASSIFIED"
    extra_properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "layer": self.layer,
            "block_name": self.block_name,
            "closed": self.closed,
            "coordinates": self.coordinates,
            "transformation": self.transformation,
            "length": round(self.length, 4),
            "area": round(self.area, 4),
            "bounding_box": self.bounding_box,
            "text": self.text,
            "dimension_value": self.dimension_value,
            "rotation": round(self.rotation, 2),
            "scale": self.scale,
            "color": self.color,
            "linetype": self.linetype,
            "handle": self.handle,
            "source_file": self.source_file,
            "status": self.status,
            **self.extra_properties,
        }
