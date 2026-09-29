from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_flooring(element: ConstructionElement) -> list[MaterialQuantity]:
    """
    Calculates flooring finishes:
    - Tile / Marble / Granite Area (sqm) with 5% wastage
    - Polymer Tile Adhesive (~5.5 kg/sqm)
    - Epoxy Grout & spacers (~0.5 kg/sqm)
    - Cement Screed Underbed (50mm 1:4 mix)
    - Skirting (rmt) along perimeter with 3% wastage
    """
    area = float(element.geometry.get("area", 0.0))
    perimeter = float(element.geometry.get("perimeter", 0.0) or element.geometry.get("skirting_length", 0.0))

    if area <= 0:
        return []

    subtype = element.subtype
    tile_wastage = 5.0
    total_area = area * (1 + tile_wastage / 100.0)

    tile_name = "600x600 mm Glazed Vitrified Tiles (GVT)"
    tile_rate = 950.0
    if "MARBLE" in subtype:
        tile_name = "Indian Green / Morwad White Marble Slabs (18mm)"
        tile_rate = 1850.0
    elif "GRANITE" in subtype:
        tile_name = "Flamed / Polished Jet Black Granite Slabs (18mm)"
        tile_rate = 2200.0
    elif "WOOD" in subtype:
        tile_name = "Laminated Wooden Flooring (8mm AC4 grade)"
        tile_rate = 1450.0

    results: list[MaterialQuantity] = []

    # 1. Tile / Stone
    results.append(
        MaterialQuantity(
            material_id=f"MAT-FLR-{element.element_id}",
            material_name=tile_name,
            category="Flooring & Tiling",
            unit="sqm",
            quantity=round(area, 2),
            wastage_percent=tile_wastage,
            total_quantity=round(total_area, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Net Floor Area {area:.2f} sqm + 5% cutting wastage",
            status=element.status,
            confidence=element.confidence,
            rate=tile_rate,
            amount=round(total_area * tile_rate, 2),
        )
    )

    # 2. Polymer Tile Adhesive (5.5 kg/sqm)
    adhesive_kg = area * 5.5
    results.append(
        MaterialQuantity(
            material_id=f"MAT-ADH-FLR-{element.element_id}",
            material_name="Polymer Modified High Strength Tile Adhesive (Type 2)",
            category="Cement & Mortar",
            unit="kg",
            quantity=round(adhesive_kg, 1),
            wastage_percent=3.0,
            total_quantity=round(adhesive_kg * 1.03, 1),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"{area:.2f} sqm x 5.5 kg/sqm",
            status=element.status,
            confidence=element.confidence,
            rate=18.0,
            amount=round(adhesive_kg * 1.03 * 18.0, 2),
        )
    )

    # 3. Epoxy Grout (0.5 kg/sqm)
    grout_kg = area * 0.50
    results.append(
        MaterialQuantity(
            material_id=f"MAT-GRT-FLR-{element.element_id}",
            material_name="Epoxy Tile Joint Grout & Spacers",
            category="Paints & Chemicals",
            unit="kg",
            quantity=round(grout_kg, 1),
            wastage_percent=3.0,
            total_quantity=round(grout_kg * 1.03, 1),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"{area:.2f} sqm x 0.5 kg/sqm",
            status=element.status,
            confidence=element.confidence,
            rate=140.0,
            amount=round(grout_kg * 1.03 * 140.0, 2),
        )
    )

    # 4. Skirting if perimeter available
    if perimeter > 0:
        tot_skirt = perimeter * 1.03
        results.append(
            MaterialQuantity(
                material_id=f"MAT-SKT-FLR-{element.element_id}",
                material_name=f"100mm High Matching Skirting for {tile_name.split()[0]}",
                category="Flooring & Tiling",
                unit="rmt",
                quantity=round(perimeter, 2),
                wastage_percent=3.0,
                total_quantity=round(tot_skirt, 2),
                source_element_id=element.element_id,
                source_element_type=element.element_type,
                calculation_basis=f"Room Perimeter {perimeter:.2f} rmt + 3% wastage",
                status=element.status,
                confidence=element.confidence,
                rate=120.0,
                amount=round(tot_skirt * 120.0, 2),
            )
        )

    return results
