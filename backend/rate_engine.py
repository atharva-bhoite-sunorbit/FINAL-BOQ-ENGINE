from __future__ import annotations

from typing import Any


def apply_rates(items: list[dict[str, Any]], rates: dict[str, Any], ohp_percent: float = 0) -> dict[str, Any]:
    for item in items:
        rate = rates.get(item["code"], {})
        material_rate = float(rate.get("material_rate", rate.get("rate", 0)))
        labour_rate = float(rate.get("labour_rate", 0))
        direct_rate = material_rate + labour_rate
        final_rate = direct_rate * (1 + ohp_percent / 100)
        item.update({
            "material_rate": material_rate,
            "labour_rate": labour_rate,
            "ohp_percent": ohp_percent,
            "final_rate": round(final_rate, 2),
            "rate": round(final_rate, 2),
            "amount": round(item["final_quantity"] * final_rate, 2),
        })
    return {"items": items, "ohp_percent": ohp_percent}
