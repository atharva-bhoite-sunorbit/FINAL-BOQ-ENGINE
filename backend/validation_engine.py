from __future__ import annotations

from typing import Any


def validate_boq(reference_items: list[dict[str, Any]], generated_items: list[dict[str, Any]], tolerance_percent: float = 1) -> dict[str, Any]:
    generated = {item.get("code") or item.get("item"): item for item in generated_items}
    rows = []
    for reference in reference_items:
        key = reference.get("code") or reference.get("item")
        reference_qty = float(reference.get("quantity", 0))
        current = generated.get(key)
        generated_qty = float(current.get("quantity", 0)) if current else 0
        difference = round(generated_qty - reference_qty, 2)
        percent = round((difference / reference_qty) * 100, 2) if reference_qty else None
        rows.append({
            "item": key, "reference_qty": reference_qty, "generated_qty": generated_qty,
            "unit": reference.get("unit"), "difference": difference, "difference_percent": percent,
            "status": "MATCH" if percent is not None and abs(percent) <= tolerance_percent else "MISMATCH",
            "formula": current.get("calculation") if current else "NOT_FOUND",
            "source_geometry": current.get("source_geometry", []) if current else [],
        })
    return {"tolerance_percent": tolerance_percent, "rows": rows, "match_count": sum(row["status"] == "MATCH" for row in rows), "mismatch_count": sum(row["status"] == "MISMATCH" for row in rows)}
