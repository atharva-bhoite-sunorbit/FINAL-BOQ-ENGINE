from __future__ import annotations

from typing import Any, Optional


def compare_revisions(
    base_elements: list[dict[str, Any]],
    revised_elements: list[dict[str, Any]],
    base_boq: Optional[list[dict[str, Any]]] = None,
    revised_boq: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Compares two drawing revisions deterministically.
    Detects added, removed, modified, and unchanged elements.
    Calculates quantity deltas for major material and work categories.
    """
    base_map = {e.get("element_id"): e for e in base_elements if e.get("element_id")}
    rev_map = {e.get("element_id"): e for e in revised_elements if e.get("element_id")}

    added_ids = [eid for eid in rev_map if eid not in base_map]
    removed_ids = [eid for eid in base_map if eid not in rev_map]
    modified_ids: list[str] = []
    unchanged_ids: list[str] = []

    for eid in rev_map:
        if eid in base_map:
            b_elem = base_map[eid]
            r_elem = rev_map[eid]
            # Check geometry changes
            bg = b_elem.get("geometry", {})
            rg = r_elem.get("geometry", {})
            diff = False
            for k in ("length", "area", "volume", "thickness", "height"):
                bv = float(bg.get(k, 0.0) or 0.0)
                rv = float(rg.get(k, 0.0) or 0.0)
                if abs(bv - rv) > 0.01:
                    diff = True
                    break
            if diff:
                modified_ids.append(eid)
            else:
                unchanged_ids.append(eid)

    # Quantity comparison on BOQ level
    quantity_deltas: list[dict[str, Any]] = []
    if base_boq and revised_boq:
        base_cat: dict[str, float] = {}
        for it in base_boq:
            mat = (it.get("material") or it.get("description") or "Work").strip().upper()
            unit = it.get("unit", "")
            key = f"{mat} ({unit})"
            base_cat[key] = base_cat.get(key, 0.0) + float(it.get("final_quantity") or it.get("total_quantity") or 0.0)

        rev_cat: dict[str, float] = {}
        for it in revised_boq:
            mat = (it.get("material") or it.get("description") or "Work").strip().upper()
            unit = it.get("unit", "")
            key = f"{mat} ({unit})"
            rev_cat[key] = rev_cat.get(key, 0.0) + float(it.get("final_quantity") or it.get("total_quantity") or 0.0)

        all_keys = set(base_cat.keys()) | set(rev_cat.keys())
        for k in sorted(all_keys):
            b_val = round(base_cat.get(k, 0.0), 2)
            r_val = round(rev_cat.get(k, 0.0), 2)
            delta = round(r_val - b_val, 2)
            pct = round((delta / b_val) * 100.0, 1) if b_val > 0 else (100.0 if delta > 0 else 0.0)
            reason = "Dimensions or elements updated"
            if len(added_ids) > 0 and delta > 0:
                reason = f"{len(added_ids)} additional structural elements detected"
            elif len(removed_ids) > 0 and delta < 0:
                reason = f"{len(removed_ids)} elements removed"
            elif len(modified_ids) > 0:
                reason = f"{len(modified_ids)} elements modified in geometry"

            quantity_deltas.append({
                "item": k,
                "base_quantity": b_val,
                "revised_quantity": r_val,
                "delta": delta,
                "percentage_change": pct,
                "reason": reason,
            })

    return {
        "summary": {
            "added_count": len(added_ids),
            "removed_count": len(removed_ids),
            "modified_count": len(modified_ids),
            "unchanged_count": len(unchanged_ids),
            "total_elements": len(rev_map),
        },
        "elements": {
            "added": added_ids,
            "removed": removed_ids,
            "modified": modified_ids,
            "unchanged": unchanged_ids,
        },
        "quantity_deltas": quantity_deltas,
    }
