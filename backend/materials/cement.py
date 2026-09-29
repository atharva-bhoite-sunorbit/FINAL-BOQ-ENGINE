from __future__ import annotations

from typing import Any
from backend.models.material_quantity import MaterialQuantity


def create_cement_item(bags: float, element_id: str, element_type: str, grade: str = "OPC 53") -> MaterialQuantity:
    wastage = 2.5
    total = bags * (1 + wastage / 100.0)
    return MaterialQuantity(
        material_id=f"MAT-CMT-{element_id}",
        material_name=f"{grade} Cement (50 kg Bag)",
        category="Cement & Aggregates",
        unit="bags",
        quantity=round(bags, 2),
        wastage_percent=wastage,
        total_quantity=round(total, 2),
        source_element_id=element_id,
        source_element_type=element_type,
        calculation_basis=f"{bags:.2f} bags required + {wastage}% wastage",
        status="DERIVED",
        confidence=0.92,
        rate=380.0,
        amount=round(total * 380.0, 2),
    )
