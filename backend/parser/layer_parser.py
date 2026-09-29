from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class LayerParser:
    def __init__(self, rules_path: Optional[Path] = None):
        path = rules_path or (DATA_DIR / "layer_rules.json")
        self.rules: list[dict[str, Any]] = []
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.rules = data.get("layer_patterns", [])
            except Exception:
                self.rules = []

    def classify_layer(self, layer_name: str) -> dict[str, Any]:
        clean_name = str(layer_name or "").strip().upper()
        for rule in self.rules:
            pattern = rule.get("pattern", "")
            if re.match(pattern, clean_name, re.IGNORECASE):
                return {
                    "layer": layer_name,
                    "element_type": rule.get("element_type", "UNKNOWN"),
                    "subtype": rule.get("subtype", "GENERIC"),
                    "material_hint": rule.get("material_hint"),
                    "default_thickness": rule.get("default_thickness"),
                    "default_width": rule.get("default_width"),
                    "default_height": rule.get("default_height"),
                    "confidence": 0.85,
                }

        # Fallback heuristic
        if any(w in clean_name for w in ("WALL", "MASONRY", "BRICK", "AAC", "BLOCK")):
            return {"layer": layer_name, "element_type": "WALL", "subtype": "BRICK_WALL", "material_hint": "BRICK", "confidence": 0.70}
        if any(w in clean_name for w in ("DOOR", "DR")):
            return {"layer": layer_name, "element_type": "DOOR", "subtype": "FLUSH_DOOR", "material_hint": "TIMBER", "confidence": 0.75}
        if any(w in clean_name for w in ("WIN", "WINDOW", "GLAZ")):
            return {"layer": layer_name, "element_type": "WINDOW", "subtype": "ALUMINIUM_WINDOW", "material_hint": "ALUMINIUM_GLASS", "confidence": 0.75}
        if any(w in clean_name for w in ("COL", "COLUMN")):
            return {"layer": layer_name, "element_type": "COLUMN", "subtype": "RCC_COLUMN", "material_hint": "CONCRETE", "confidence": 0.75}
        if any(w in clean_name for w in ("BEAM", "RCC")):
            return {"layer": layer_name, "element_type": "BEAM", "subtype": "RCC_BEAM", "material_hint": "CONCRETE", "confidence": 0.75}
        if any(w in clean_name for w in ("SLAB", "FLOOR", "ROOF")):
            return {"layer": layer_name, "element_type": "SLAB", "subtype": "RCC_SLAB", "material_hint": "CONCRETE", "confidence": 0.70}

        return {"layer": layer_name, "element_type": "UNCLASSIFIED", "confidence": 0.30}
