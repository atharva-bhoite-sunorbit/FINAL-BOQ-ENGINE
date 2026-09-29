from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_plumbing(element: ConstructionElement) -> list[MaterialQuantity]:
    """
    Calculates plumbing water supply and drainage pipe quantities when CAD evidence is present.
    """
    geo = element.geometry
    subtype = element.subtype.upper()
    quantities: list[MaterialQuantity] = []

    length = float(geo.get("length", 0.0) or (geo.get("perimeter", 0.0) if geo.get("perimeter") else 0.0))
    if length <= 0:
        return quantities

    wastage = 5.0
    tot_len = length * (1 + wastage / 100.0)

    if "DRAIN" in subtype or "SOIL" in subtype or "WASTE" in subtype or "SEWER" in subtype:
        quantities.append(
            MaterialQuantity(
                material_id=f"MAT-PLM-DRN-{element.element_id}",
                material_name="110mm / 75mm SWR PVC Soil & Waste Drainage Piping with Rubber Ring Joints",
                category="Plumbing & Drainage",
                unit="rm",
                quantity=round(length, 2),
                wastage_percent=wastage,
                total_quantity=round(tot_len, 2),
                source_element_id=element.element_id,
                source_element_type=element.element_type,
                source_entities=element.source_entities,
                source_layers=element.source_layers,
                calculation_basis=f"Drainage run length {length:.2f}m + {wastage}% wastage",
                status="MEASURED",
                confidence=element.confidence,
                rate=320.0,
                amount=round(tot_len * 320.0, 2),
            )
        )
    else:
        quantities.append(
            MaterialQuantity(
                material_id=f"MAT-PLM-WTR-{element.element_id}",
                material_name="CPVC Hot & Cold Water Supply Piping (SDR 11 - 25mm/20mm dia)",
                category="Plumbing & Drainage",
                unit="rm",
                quantity=round(length, 2),
                wastage_percent=wastage,
                total_quantity=round(tot_len, 2),
                source_element_id=element.element_id,
                source_element_type=element.element_type,
                source_entities=element.source_entities,
                source_layers=element.source_layers,
                calculation_basis=f"Water pipe run length {length:.2f}m + {wastage}% wastage",
                status="MEASURED",
                confidence=element.confidence,
                rate=210.0,
                amount=round(tot_len * 210.0, 2),
            )
        )

    return quantities
