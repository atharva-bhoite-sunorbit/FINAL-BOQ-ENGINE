from __future__ import annotations

from typing import Any
from backend.models.material_quantity import MaterialQuantity


def create_sand_item(volume_cum: float, element_id: str, element_type: str) -> MaterialQuantity:
    wastage = 5.0
    total = volume_cum * (1 + wastage / 100.0)
    return MaterialQuantity(
        material_id=f"MAT-SND-{element_id}",
        material_name="River Sand / Manufactured M-Sand",
        category="Cement & Aggregates",
        unit="cum",
        quantity=round(volume_cum, 3),
        wastage_percent=wastage,
        total_quantity=round(total, 3),
        source_element_id=element_id,
        source_element_type=element_type,
        calculation_basis=f"{volume_cum:.3f} cum sand + {wastage}% wastage",
        status="DERIVED",
        confidence=0.92,
        rate=1850.0,
        amount=round(total * 1850.0, 2),
    )
