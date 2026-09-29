from __future__ import annotations

from typing import Any, Sequence


class DeductionEngine:
    @staticmethod
    def calculate_opening_deduction(
        opening_width_m: float,
        opening_height_m: float,
        wall_thickness_m: float,
        sides_for_surface: int = 2,
    ) -> dict[str, float]:
        face_area = opening_width_m * opening_height_m
        volume_m3 = face_area * wall_thickness_m
        surface_area_m2 = face_area * sides_for_surface

        return {
            "opening_width_m": round(opening_width_m, 4),
            "opening_height_m": round(opening_height_m, 4),
            "face_area_m2": round(face_area, 4),
            "deduction_volume_m3": round(volume_m3, 4),
            "deduction_surface_area_m2": round(surface_area_m2, 4),
        }

    @staticmethod
    def apply_deductions_to_wall(
        gross_volume_m3: float,
        gross_surface_area_m2: float,
        openings: Sequence[dict[str, Any]],
        wall_thickness_m: float,
    ) -> dict[str, Any]:
        total_deduction_vol = 0.0
        total_deduction_surf = 0.0
        applied_openings = []

        for op in openings:
            w = float(op.get("width_m", op.get("width", 0.9)))
            h = float(op.get("height_m", op.get("height", 2.1)))
            ded = DeductionEngine.calculate_opening_deduction(w, h, wall_thickness_m)
            total_deduction_vol += ded["deduction_volume_m3"]
            total_deduction_surf += ded["deduction_surface_area_m2"]
            applied_openings.append(op.get("opening_id", "OPENING"))

        net_vol = gross_volume_m3 - total_deduction_vol
        net_surf = gross_surface_area_m2 - total_deduction_surf

        is_valid = (net_vol >= 0 and net_surf >= 0)

        return {
            "gross_volume_m3": round(gross_volume_m3, 4),
            "deduction_volume_m3": round(total_deduction_vol, 4),
            "net_volume_m3": round(max(0.0, net_vol), 4),
            "gross_surface_area_m2": round(gross_surface_area_m2, 4),
            "deduction_surface_area_m2": round(total_deduction_surf, 4),
            "net_surface_area_m2": round(max(0.0, net_surf), 4),
            "applied_openings": applied_openings,
            "is_valid": is_valid,
            "warning": None if is_valid else "INVALID_QUANTITY: Opening deduction exceeds gross quantity",
        }
