from __future__ import annotations

import math
from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_gypsum_partition(
    element: ConstructionElement,
    sides: int = 2,
    layers_per_side: int = 1,
    stud_spacing_m: float = 0.61,  # 610mm c/c
) -> list[MaterialQuantity]:
    """
    Calculates drywall / gypsum board partition materials:
    - Gypsum plasterboards (sqm) = length * height * sides * layers
    - GI Studs (rmt) = ((length / spacing) + 1) * height
    - GI Tracks (rmt) = length * 2 (top + bottom)
    - Acoustic Glass Wool insulation (sqm) = length * height
    - Drywall screws (nos) = 15 nos per sqm of board
    - Joint compound (kg) = 0.25 kg per sqm of board
    - Aluminium Skirting (rmt) = length * sides
    """
    length = float(element.geometry.get("length", 0.0))
    height = float(element.geometry.get("height", 3.0))
    if length <= 0:
        area = float(element.geometry.get("area", 0.0))
        length = area / height if height > 0 else 0.0

    if length <= 0:
        return []

    wall_area = length * height
    board_area = wall_area * sides * layers_per_side
    num_studs = math.ceil(length / stud_spacing_m) + 1
    stud_length_rmt = num_studs * height
    track_length_rmt = length * 2.0
    insulation_area = wall_area
    screws_count = board_area * 15.0
    joint_compound_kg = board_area * 0.25
    skirting_rmt = length * sides

    results: list[MaterialQuantity] = []

    # 1. Gypsum Board
    board_wastage = 5.0
    tot_board = board_area * (1 + board_wastage / 100.0)
    results.append(
        MaterialQuantity(
            material_id=f"MAT-GYP-{element.element_id}",
            material_name="12.5 mm Tapered Edge Gypsum Plasterboard",
            category="Partitions & Drywall",
            unit="sqm",
            quantity=round(board_area, 2),
            wastage_percent=board_wastage,
            total_quantity=round(tot_board, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Length {length:.2f}m x {height:.2f}m x {sides} sides x {layers_per_side} layers + 5% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=380.0,
            amount=round(tot_board * 380.0, 2),
        )
    )

    # 2. GI Studs
    results.append(
        MaterialQuantity(
            material_id=f"MAT-GIS-{element.element_id}",
            material_name="GI Vertical Studs 48mm / 70mm (0.55mm BMT)",
            category="Metal Framework",
            unit="rmt",
            quantity=round(stud_length_rmt, 2),
            wastage_percent=3.0,
            total_quantity=round(stud_length_rmt * 1.03, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"{num_studs} studs @ {int(stud_spacing_m*1000)}mm c/c x {height:.2f}m height",
            status=element.status,
            confidence=element.confidence,
            rate=85.0,
            amount=round(stud_length_rmt * 1.03 * 85.0, 2),
        )
    )

    # 3. GI Tracks
    results.append(
        MaterialQuantity(
            material_id=f"MAT-GIT-{element.element_id}",
            material_name="GI Floor & Ceiling Track Channels (0.55mm BMT)",
            category="Metal Framework",
            unit="rmt",
            quantity=round(track_length_rmt, 2),
            wastage_percent=3.0,
            total_quantity=round(track_length_rmt * 1.03, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Floor + Ceiling runners = {length:.2f}m x 2",
            status=element.status,
            confidence=element.confidence,
            rate=80.0,
            amount=round(track_length_rmt * 1.03 * 80.0, 2),
        )
    )

    # 4. Glass Wool Insulation
    results.append(
        MaterialQuantity(
            material_id=f"MAT-GWL-{element.element_id}",
            material_name="50mm Resin Bonded Acoustic Glasswool (24 kg/m3)",
            category="Insulation",
            unit="sqm",
            quantity=round(insulation_area, 2),
            wastage_percent=3.0,
            total_quantity=round(insulation_area * 1.03, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Cavity area = {length:.2f}m x {height:.2f}m",
            status=element.status,
            confidence=element.confidence,
            rate=140.0,
            amount=round(insulation_area * 1.03 * 140.0, 2),
        )
    )

    # 5. Screws & Fasteners
    results.append(
        MaterialQuantity(
            material_id=f"MAT-SCR-{element.element_id}",
            material_name="Self-Drilling Drywall Screws 25mm",
            category="Hardware & Fasteners",
            unit="nos",
            quantity=round(screws_count, 0),
            wastage_percent=5.0,
            total_quantity=round(screws_count * 1.05, 0),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"{board_area:.1f} sqm board x 15 screws/sqm",
            status=element.status,
            confidence=element.confidence,
            rate=1.20,
            amount=round(screws_count * 1.05 * 1.20, 2),
        )
    )

    # 6. Jointing Compound
    results.append(
        MaterialQuantity(
            material_id=f"MAT-JNT-{element.element_id}",
            material_name="Drywall Jointing Compound & Fiber Tape",
            category="Paints & Chemicals",
            unit="kg",
            quantity=round(joint_compound_kg, 1),
            wastage_percent=3.0,
            total_quantity=round(joint_compound_kg * 1.03, 1),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"{board_area:.1f} sqm board x 0.25 kg/sqm",
            status=element.status,
            confidence=element.confidence,
            rate=45.0,
            amount=round(joint_compound_kg * 1.03 * 45.0, 2),
        )
    )

    # 7. Aluminium Skirting
    results.append(
        MaterialQuantity(
            material_id=f"MAT-SKT-{element.element_id}",
            material_name="50mm Anodized Aluminium Skirting with Clips",
            category="Glass & Aluminium",
            unit="rmt",
            quantity=round(skirting_rmt, 2),
            wastage_percent=3.0,
            total_quantity=round(skirting_rmt * 1.03, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Length {length:.2f}m x {sides} sides",
            status=element.status,
            confidence=element.confidence,
            rate=185.0,
            amount=round(skirting_rmt * 1.03 * 185.0, 2),
        )
    )

    return results


def calculate_gypsum(
    element: ConstructionElement,
    sides: int = 2,
    layers_per_side: int = 2,
    stud_spacing_m: float = 0.61,
) -> list[MaterialQuantity]:
    annot = " ".join(element.source_annotations).upper()
    if "SINGLE" in annot or "1 LAYER" in annot:
        layers = 1
    else:
        layers = layers_per_side
    return calculate_gypsum_partition(element, sides=sides, layers_per_side=layers, stud_spacing_m=stud_spacing_m)


__all__ = ["calculate_gypsum_partition", "calculate_gypsum"]
