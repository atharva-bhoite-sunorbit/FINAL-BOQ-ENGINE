from __future__ import annotations

import re
from typing import Any, Optional
from backend.models.cad_entity import CADEntity


class TextParser:
    def __init__(self, entities: list[CADEntity]):
        self.text_entities = [e for e in entities if e.entity_type in {"TEXT", "MTEXT"} and e.text]

    def extract_specifications(self) -> list[dict[str, Any]]:
        specs = []
        for e in self.text_entities:
            raw_text = str(e.text).strip()
            parsed = self.parse_single_annotation(raw_text)
            if parsed:
                parsed["entity_id"] = e.entity_id
                parsed["handle"] = e.handle
                parsed["layer"] = e.layer
                parsed["raw_text"] = raw_text
                parsed["location"] = e.coordinates[0] if e.coordinates else None
                specs.append(parsed)
        return specs

    @staticmethod
    def parse_single_annotation(text: str) -> Optional[dict[str, Any]]:
        upper = text.upper()
        res: dict[str, Any] = {}

        # 1. Thickness / Material Detection (e.g., "75MM GYPSUM PARTITION", "150MM AAC BLOCK", "10MM TOUGHENED GLASS")
        m_thick = re.search(r"(\d+)\s*(?:MM|M)\s+([A-Z0-9\s\-]+)", upper)
        if m_thick:
            num = float(m_thick.group(1))
            mat_desc = m_thick.group(2).strip()
            res["thickness_m"] = num / 1000.0
            res["material_description"] = mat_desc

            if "GYPSUM" in mat_desc:
                res["element_type"] = "PARTITION"
                res["subtype"] = "GYPSUM_PARTITION"
                res["material"] = "GYPSUM"
            elif "AAC" in mat_desc or "BLOCK" in mat_desc:
                res["element_type"] = "WALL"
                res["subtype"] = "AAC_BLOCK_WALL"
                res["material"] = "AAC_BLOCK"
            elif "GLASS" in mat_desc:
                res["element_type"] = "PARTITION"
                res["subtype"] = "GLASS_ALUMINIUM_PARTITION"
                res["material"] = "TOUGHENED_GLASS"
            return res

        # 2. Reinforcement Bar Callout (e.g. "8T16", "4-16#", "4Y12", "T8 @150 C/C")
        m_rebar = re.search(r"(\d+)\s*[TY#]\s*(\d+)", upper)
        if m_rebar:
            res["bar_count"] = int(m_rebar.group(1))
            res["bar_diameter_mm"] = int(m_rebar.group(2))
            res["element_type"] = "REINFORCEMENT"
            return res

        m_stirrup = re.search(r"[TY#]\s*(\d+)\s*@\s*(\d+)", upper)
        if m_stirrup:
            res["stirrup_diameter_mm"] = int(m_stirrup.group(1))
            res["stirrup_spacing_mm"] = int(m_stirrup.group(2))
            res["element_type"] = "STIRRUP"
            return res

        # 3. Concrete Grade (e.g. "RCC M25", "M30 GRADE")
        m_conc = re.search(r"(?:RCC\s+)?(M\d{2})", upper)
        if m_conc:
            res["concrete_grade"] = m_conc.group(1)
            res["element_type"] = "CONCRETE"
            return res

        # 4. Room labels (e.g. "LIVING ROOM", "BEDROOM 1", "TOILET", "KITCHEN")
        for room_keyword in ("LIVING", "BEDROOM", "KITCHEN", "TOILET", "BATH", "BALCONY", "OFFICE", "CONFERENCE", "LOBBY"):
            if room_keyword in upper:
                res["room_name"] = upper.strip()
                res["element_type"] = "ROOM"
                return res

        return None
