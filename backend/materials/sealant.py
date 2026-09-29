from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_sealant(element: ConstructionElement, wastage_percent: float = 5.0) -> list[MaterialQuantity]:
    """
    Calculates weather-proof and structural silicone sealant along glazed partitions,
    window reveals, and expansion/control joints.
    """
    geo = element.geometry
    length = float(geo.get("length", 0.0) or (geo.get("perimeter", 0.0) if geo.get("perimeter") else 0.0))
    if length <= 0:
        area = float(geo.get("area", 0.0))
        if area > 0:
            length = (area ** 0.5) * 4.0

    if length <= 0:
        return []

    # 1 cartridge (310 ml) typically seals ~ 3 rmt of 10mm x 10mm joint
    cartridges = length / 3.0
    tot_cartridges = cartridges * (1 + wastage_percent / 100.0)

    return [
        MaterialQuantity(
            material_id=f"MAT-SLN-{element.element_id}",
            material_name="Weatherproof Neutral Cure Silicone Sealant (310ml Sausage/Cartridge)",
            category="Hardware & Sealants",
            unit="nos",
            quantity=round(cartridges, 2),
            wastage_percent=wastage_percent,
            total_quantity=round(tot_cartridges, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            source_entities=element.source_entities,
            source_layers=element.source_layers,
            calculation_basis=f"Joint length {length:.2f}m / 3m per cartridge = {cartridges:.2f} nos + {wastage_percent}% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=280.0,
            amount=round(tot_cartridges * 280.0, 2),
        )
    ]
