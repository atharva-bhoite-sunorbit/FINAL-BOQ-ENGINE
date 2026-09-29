from __future__ import annotations

from typing import Any
from backend.models.cad_entity import CADEntity


class DrawingViewParser:
    def __init__(self, entities: list[CADEntity]):
        self.entities = entities

    def detect_views(self) -> list[dict[str, Any]]:
        views = []
        text_entities = [e for e in self.entities if e.entity_type in {"TEXT", "MTEXT"} and e.text]

        # Scan for drawing view titles
        for t in text_entities:
            upper = str(t.text).upper().strip()
            view_type = None

            if any(k in upper for k in ("GROUND FLOOR", "FIRST FLOOR", "TYPICAL FLOOR", "TERRACE FLOOR", "FLOOR PLAN", "LAYOUT PLAN")):
                view_type = "ARCHITECTURAL_PLAN"
            elif any(k in upper for k in ("BEAM LAYOUT", "COLUMN LAYOUT", "SLAB DETAIL", "FOUNDATION PLAN", "STRUCTURAL PLAN")):
                view_type = "STRUCTURAL_PLAN"
            elif "FURNITURE" in upper:
                view_type = "FURNITURE_PLAN"
            elif any(k in upper for k in ("RCP", "REFLECTED CEILING")):
                view_type = "RCP"
            elif "ELEVATION" in upper:
                view_type = "ELEVATION"
            elif any(k in upper for k in ("SECTION", "SEC-")):
                view_type = "SECTION"
            elif any(k in upper for k in ("SCHEDULE", "DOOR SCHEDULE", "WINDOW SCHEDULE", "COLUMN SCHEDULE")):
                view_type = "SCHEDULE"
            elif any(k in upper for k in ("LEGEND", "SYMBOLS")):
                view_type = "LEGEND"
            elif "TITLE" in upper:
                view_type = "TITLE_BLOCK"

            if view_type:
                loc = t.coordinates[0] if t.coordinates else [0.0, 0.0]
                views.append({
                    "view_type": view_type,
                    "title": upper,
                    "center": loc,
                    "entity_id": t.entity_id,
                })

        if not views:
            views.append({
                "view_type": "ARCHITECTURAL_PLAN",
                "title": "PRIMARY_MODEL_VIEW",
                "center": [0.0, 0.0],
                "entity_id": None,
            })

        return views
