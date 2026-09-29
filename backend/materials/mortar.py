from __future__ import annotations

from typing import Any
from backend.models.material_quantity import MaterialQuantity


def calculate_mortar_mix(
    volume_cum: float,
    ratio: str = "1:6",
    element_id: str = "E001",
    element_type: str = "WALL",
) -> list[MaterialQuantity]:
    """Calculates cement and sand quantities for a given wet volume and mix ratio (e.g. 1:4, 1:6)."""
    # Dry volume factor for mortar is typically 1.33
    dry_volume = volume_cum * 1.33
    
    parts = [float(p) for p in ratio.split(":")]
    total_parts = sum(parts)
    cement_ratio = parts[0] / total_parts
    sand_ratio = parts[1] / total_parts

    cement_cum = dry_volume * cement_ratio
    # 1 cum cement = 1440 kg = ~28.8 bags of 50kg
    cement_bags = cement_cum * 28.8
    sand_cum = dry_volume * sand_ratio

    return [
        MaterialQuantity(
            material_id=f"MAT-CMT-{element_id}",
            material_name=f"OPC / PPC Cement for Mortar ({ratio})",
            category="Cement & Aggregates",
            unit="bags",
            quantity=round(cement_bags, 2),
            wastage_percent=2.5,
            total_quantity=round(cement_bags * 1.025, 2),
            source_element_id=element_id,
            source_element_type=element_type,
            calculation_basis=f"Dry vol {dry_volume:.3f} cum x {ratio} mix",
            status="DERIVED",
            confidence=0.92,
            rate=380.0,
            amount=round(cement_bags * 1.025 * 380.0, 2),
        ),
        MaterialQuantity(
            material_id=f"MAT-SND-{element_id}",
            material_name=f"Screened Plaster/Masonry Sand for Mortar ({ratio})",
            category="Cement & Aggregates",
            unit="cum",
            quantity=round(sand_cum, 3),
            wastage_percent=5.0,
            total_quantity=round(sand_cum * 1.05, 3),
            source_element_id=element_id,
            source_element_type=element_type,
            calculation_basis=f"Dry vol {dry_volume:.3f} cum x {ratio} mix",
            status="DERIVED",
            confidence=0.92,
            rate=1850.0,
            amount=round(sand_cum * 1.05 * 1850.0, 2),
        ),
    ]
