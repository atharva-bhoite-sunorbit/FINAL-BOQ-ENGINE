from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_insulation(element: ConstructionElement, wastage_percent: float = 5.0) -> list[MaterialQuantity]:
    """
    Calculates acoustic and thermal insulation (Glasswool / Rockwool 50mm)
    for drywalls, partitions, ceilings, and roofs.
    """
    geo = element.geometry
    area = float(geo.get("area", 0.0))
    if area <= 0:
        length = float(geo.get("length", 0.0))
        height = float(geo.get("height", 3.0) or 3.0)
        area = length * height

    if area <= 0:
        return []

    tot_area = area * (1 + wastage_percent / 100.0)

    return [
        MaterialQuantity(
            material_id=f"MAT-INS-{element.element_id}",
            material_name="50mm Thick Resin Bonded Glasswool Insulation (24 kg/m3 Density)",
            category="Insulation",
            unit="m2",
            quantity=round(area, 4),
            wastage_percent=wastage_percent,
            total_quantity=round(tot_area, 4),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            source_entities=element.source_entities,
            source_layers=element.source_layers,
            calculation_basis=f"Surface area {area:.2f} m2 + {wastage_percent}% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=165.0,
            amount=round(tot_area * 165.0, 2),
        )
    ]
