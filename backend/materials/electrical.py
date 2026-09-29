from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_electrical(element: ConstructionElement) -> list[MaterialQuantity]:
    """
    Calculates electrical point wiring, conduits, and accessories only when CAD evidence is present.
    """
    geo = element.geometry
    subtype = element.subtype.upper()
    quantities: list[MaterialQuantity] = []

    if "POINT" in subtype or "LIGHT" in subtype or "SWITCH" in subtype or "SOCKET" in subtype:
        # Point wiring
        count = float(geo.get("count", 1.0) or 1.0)
        quantities.append(
            MaterialQuantity(
                material_id=f"MAT-ELE-PT-{element.element_id}",
                material_name="Concealed Electrical Point Wiring with FRLS Copper Wires & Modular Switch",
                category="Electrical & Low Voltage",
                unit="points",
                quantity=count,
                wastage_percent=0.0,
                total_quantity=count,
                source_element_id=element.element_id,
                source_element_type=element.element_type,
                source_entities=element.source_entities,
                source_layers=element.source_layers,
                calculation_basis=f"CAD detected electrical point instance count = {int(count)}",
                status="MEASURED",
                confidence=element.confidence,
                rate=950.0,
                amount=count * 950.0,
            )
        )
    elif "CONDUIT" in subtype or "CABLE" in subtype or "TRAY" in subtype:
        length = float(geo.get("length", 0.0) or (geo.get("perimeter", 0.0) if geo.get("perimeter") else 0.0))
        if length > 0:
            wastage = 5.0
            tot_len = length * (1 + wastage / 100.0)
            quantities.append(
                MaterialQuantity(
                    material_id=f"MAT-ELE-CND-{element.element_id}",
                    material_name="Heavy Duty Rigid PVC Electrical Conduit (25mm dia) with Pull Wire",
                    category="Electrical & Low Voltage",
                    unit="rm",
                    quantity=round(length, 2),
                    wastage_percent=wastage,
                    total_quantity=round(tot_len, 2),
                    source_element_id=element.element_id,
                    source_element_type=element.element_type,
                    source_entities=element.source_entities,
                    source_layers=element.source_layers,
                    calculation_basis=f"Conduit linear length {length:.2f}m + {wastage}% wastage",
                    status="MEASURED",
                    confidence=element.confidence,
                    rate=85.0,
                    amount=round(tot_len * 85.0, 2),
                )
            )

    return quantities
