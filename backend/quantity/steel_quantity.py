from __future__ import annotations

from typing import Any, Optional


def unit_weight_kg_per_meter(diameter_mm: float) -> float:
    """Standard construction formula: D^2 / 162 kg per meter."""
    return (diameter_mm ** 2) / 162.0


def calculate_bar_weight(
    diameter_mm: float,
    length_m: float,
    bar_count: int = 1,
    lap_length_m: float = 0.0,
) -> dict[str, Any]:
    w_per_m = unit_weight_kg_per_meter(diameter_mm)
    effective_length = (length_m + lap_length_m) * bar_count
    total_weight_kg = effective_length * w_per_m

    return {
        "diameter_mm": diameter_mm,
        "bar_count": bar_count,
        "length_per_bar_m": round(length_m, 4),
        "lap_length_m": round(lap_length_m, 4),
        "total_length_m": round(effective_length, 4),
        "unit_weight_kg_m": round(w_per_m, 4),
        "total_weight_kg": round(total_weight_kg, 4),
        "status": "MEASURED",
    }


def calculate_reinforcement_from_annotations(
    annotations: list[dict[str, Any]],
    element_length_m: float,
) -> dict[str, Any]:
    """
    Parses rebar specifications from drawing annotations (e.g. '8T16', 'T8 @150').
    If no reinforcement data is present, returns status = 'NOT_AVAILABLE' without fabricating steel.
    """
    bars_found = []
    total_kg = 0.0

    for a in annotations:
        if a.get("bar_count") and a.get("bar_diameter_mm"):
            cnt = a["bar_count"]
            dia = a["bar_diameter_mm"]
            res = calculate_bar_weight(dia, element_length_m, cnt)
            bars_found.append(res)
            total_kg += res["total_weight_kg"]

    if not bars_found:
        return {
            "total_weight_kg": 0.0,
            "total_weight_mt": 0.0,
            "status": "NOT_AVAILABLE",
            "remarks": "Reinforcement details absent in drawing annotations/schedules; steel not fabricated.",
            "bars": [],
        }

    return {
        "total_weight_kg": round(total_kg, 2),
        "total_weight_mt": round(total_kg / 1000.0, 4),
        "status": "DERIVED",
        "remarks": f"Derived from {len(bars_found)} rebar callout(s).",
        "bars": bars_found,
    }
