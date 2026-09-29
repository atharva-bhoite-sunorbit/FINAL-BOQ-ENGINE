from __future__ import annotations

from typing import Any, Sequence
from backend.models.construction_element import ConstructionElement
from backend.quantity.area_calculator import calculate_polygon_area, calculate_wall_surface_area
from backend.quantity.volume_calculator import (
    calculate_wall_volume,
    calculate_column_volume,
    calculate_beam_volume,
    calculate_slab_volume,
    calculate_footing_volume,
)
from backend.quantity.length_calculator import calculate_segments_total_length
from backend.quantity.deduction_engine import DeductionEngine
from backend.quantity.wastage_engine import WastageEngine
from backend.quantity.unit_converter import to_meters, from_meters, to_sqm, from_sqm, to_cum, from_cum


class QuantityEngine:
    def __init__(self):
        self.deduction_engine = DeductionEngine()
        self.wastage_engine = WastageEngine()

    def process_element(self, element: ConstructionElement, openings: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
        etype = element.element_type
        geo = element.geometry
        units = element.extra.get("units", "m")

        length_m = to_meters(geo.get("length", 0.0), units)
        height_m = to_meters(geo.get("height", 3.0), units)
        thickness_m = to_meters(geo.get("thickness", 0.15), units)
        width_m = to_meters(geo.get("width", 0.0), units)
        raw_area = geo.get("area", 0.0)
        area_m2 = to_sqm(raw_area, f"{units}2") if units != "m" else raw_area

        res = {
            "element_id": element.element_id,
            "element_type": etype,
            "subtype": element.subtype,
            "gross_quantity": 0.0,
            "deduction_quantity": 0.0,
            "net_quantity": 0.0,
            "unit": "m2",
            "calculation_basis": "",
            "status": element.status,
            "confidence": element.confidence,
        }

        if etype in {"WALL", "PARTITION"}:
            gross_vol = calculate_wall_volume(length_m, height_m, thickness_m)
            gross_surf = calculate_wall_surface_area(length_m, height_m, sides=2)

            if openings:
                ded_res = self.deduction_engine.apply_deductions_to_wall(
                    gross_vol, gross_surf, openings, thickness_m
                )
                res["gross_quantity"] = ded_res["gross_volume_m3"]
                res["deduction_quantity"] = ded_res["deduction_volume_m3"]
                res["net_quantity"] = ded_res["net_volume_m3"]
                res["gross_surface_area_m2"] = ded_res["gross_surface_area_m2"]
                res["deduction_surface_area_m2"] = ded_res["deduction_surface_area_m2"]
                res["net_surface_area_m2"] = ded_res["net_surface_area_m2"]
                res["unit"] = "m3"
                res["calculation_basis"] = (
                    f"Wall {length_m:.2f}m × {height_m:.2f}m × {thickness_m:.2f}m "
                    f"- {len(openings)} opening(s) ({ded_res['deduction_volume_m3']:.3f} m3)"
                )
            else:
                res["gross_quantity"] = gross_vol
                res["deduction_quantity"] = 0.0
                res["net_quantity"] = gross_vol
                res["gross_surface_area_m2"] = gross_surf
                res["deduction_surface_area_m2"] = 0.0
                res["net_surface_area_m2"] = gross_surf
                res["unit"] = "m3"
                res["calculation_basis"] = f"Wall {length_m:.2f}m × {height_m:.2f}m × {thickness_m:.2f}m"

        elif etype in {"SLAB", "FLOOR", "ROOF", "CEILING"}:
            res["gross_quantity"] = area_m2
            res["deduction_quantity"] = 0.0
            res["net_quantity"] = area_m2
            res["unit"] = "m2"
            res["calculation_basis"] = f"Plan Area: {area_m2:.2f} m2"

        elif etype == "COLUMN":
            vol = calculate_column_volume(width_m or 0.3, thickness_m or 0.3, height_m)
            res["gross_quantity"] = vol
            res["deduction_quantity"] = 0.0
            res["net_quantity"] = vol
            res["unit"] = "m3"
            res["calculation_basis"] = f"Column {(width_m or 0.3):.2f}m × {(thickness_m or 0.3):.2f}m × {height_m:.2f}m"

        elif etype == "BEAM":
            vol = calculate_beam_volume(length_m, width_m or 0.23, thickness_m or 0.45)
            res["gross_quantity"] = vol
            res["deduction_quantity"] = 0.0
            res["net_quantity"] = vol
            res["unit"] = "m3"
            res["calculation_basis"] = f"Beam {length_m:.2f}m × {(width_m or 0.23):.2f}m × {(thickness_m or 0.45):.2f}m"

        elif etype in {"DOOR", "WINDOW"}:
            res["gross_quantity"] = 1.0
            res["deduction_quantity"] = 0.0
            res["net_quantity"] = 1.0
            res["unit"] = "nos"
            res["calculation_basis"] = "Count (1 instance)"

        else:
            res["gross_quantity"] = length_m or area_m2 or 1.0
            res["deduction_quantity"] = 0.0
            res["net_quantity"] = res["gross_quantity"]
            res["unit"] = "m" if length_m else "nos"
            res["calculation_basis"] = "Geometric Takeoff"

        return res
