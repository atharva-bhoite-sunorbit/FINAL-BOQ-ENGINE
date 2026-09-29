from __future__ import annotations

from typing import Any
from backend.models.cad_entity import CADEntity


class DimensionParser:
    def __init__(self, entities: list[CADEntity]):
        self.dim_entities = [e for e in entities if e.entity_type == "DIMENSION"]

    def extract_dimensions(self) -> list[dict[str, Any]]:
        results = []
        for e in self.dim_entities:
            meas = e.dimension_value
            text = (e.text or "").strip()
            # If text is an explicit override (e.g., "3000" or "3.00m"), try to extract number
            if text and text != "<>":
                import re
                m = re.search(r"(\d+(?:\.\d+)?)", text)
                if m:
                    meas = float(m.group(1))

            if meas is not None and meas > 0:
                results.append({
                    "entity_id": e.entity_id,
                    "handle": e.handle,
                    "layer": e.layer,
                    "measurement": meas,
                    "text_override": text if text != "<>" else None,
                    "location": e.coordinates[0] if e.coordinates else None,
                })
        return results
