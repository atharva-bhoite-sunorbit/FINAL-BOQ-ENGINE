from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class WastageEngine:
    def __init__(self, rules_path: Optional[Path] = None):
        path = rules_path or (DATA_DIR / "wastage_rules.json")
        self.rules: dict[str, float] = {}
        if path.exists():
            try:
                self.rules = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.rules = {}

    def get_wastage_percent(self, material_name: str) -> float:
        clean = str(material_name or "").strip()
        # Exact match
        if clean in self.rules:
            return float(self.rules[clean])
        # Case-insensitive substring match
        clean_upper = clean.upper()
        for k, v in self.rules.items():
            if k.upper() in clean_upper or clean_upper in k.upper():
                return float(v)
        return float(self.rules.get("General", 3.0))

    def apply_wastage(self, net_quantity: float, material_name: str) -> dict[str, float]:
        pct = self.get_wastage_percent(material_name)
        wastage_qty = round(net_quantity * (pct / 100.0), 4)
        total_qty = round(net_quantity + wastage_qty, 4)

        return {
            "net_quantity": round(net_quantity, 4),
            "wastage_percent": pct,
            "wastage_quantity": wastage_qty,
            "total_quantity": total_qty,
        }
