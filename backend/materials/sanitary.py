from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_sanitary(element: ConstructionElement) -> list[MaterialQuantity]:
    """
    Calculates sanitary fixtures and CP fittings based on CAD blocks / identified points.
    """
    geo = element.geometry
    subtype = element.subtype.upper()
    count = float(geo.get("count", 1.0) or 1.0)
    quantities: list[MaterialQuantity] = []

    if "WC" in subtype or "TOILET" in subtype or "COMMODE" in subtype:
        quantities.append(
            MaterialQuantity(
                material_id=f"MAT-SAN-WC-{element.element_id}",
                material_name="Wall-Hung / Floor Mounted EWC with Soft-Close Seat & Dual-Flush Concealed Cistern",
                category="Sanitary Fixtures & CP Fittings",
                unit="sets",
                quantity=count,
                wastage_percent=0.0,
                total_quantity=count,
                source_element_id=element.element_id,
                source_element_type=element.element_type,
                source_entities=element.source_entities,
                source_layers=element.source_layers,
                calculation_basis=f"CAD detected EWC unit count = {int(count)}",
                status="MEASURED",
                confidence=element.confidence,
                rate=9500.0,
                amount=count * 9500.0,
            )
        )
    elif "BASIN" in subtype or "SINK" in subtype or "WASH" in subtype:
        quantities.append(
            MaterialQuantity(
                material_id=f"MAT-SAN-BSN-{element.element_id}",
                material_name="Vitreous China Wash Basin with CP Brass Pillar Cock & Bottle Trap",
                category="Sanitary Fixtures & CP Fittings",
                unit="sets",
                quantity=count,
                wastage_percent=0.0,
                total_quantity=count,
                source_element_id=element.element_id,
                source_element_type=element.element_type,
                source_entities=element.source_entities,
                source_layers=element.source_layers,
                calculation_basis=f"CAD detected Wash Basin count = {int(count)}",
                status="MEASURED",
                confidence=element.confidence,
                rate=4200.0,
                amount=count * 4200.0,
            )
        )
    elif "SHOWER" in subtype:
        quantities.append(
            MaterialQuantity(
                material_id=f"MAT-SAN-SHW-{element.element_id}",
                material_name="Overhead Rain Shower with Wall Flange and Single Lever Diverter",
                category="Sanitary Fixtures & CP Fittings",
                unit="sets",
                quantity=count,
                wastage_percent=0.0,
                total_quantity=count,
                source_element_id=element.element_id,
                source_element_type=element.element_type,
                source_entities=element.source_entities,
                source_layers=element.source_layers,
                calculation_basis=f"CAD detected Shower point count = {int(count)}",
                status="MEASURED",
                confidence=element.confidence,
                rate=3800.0,
                amount=count * 3800.0,
            )
        )
    else:
        quantities.append(
            MaterialQuantity(
                material_id=f"MAT-SAN-GEN-{element.element_id}",
                material_name="Sanitary Appliance Complete with CP Brass Angle Cock and Connections",
                category="Sanitary Fixtures & CP Fittings",
                unit="nos",
                quantity=count,
                wastage_percent=0.0,
                total_quantity=count,
                source_element_id=element.element_id,
                source_element_type=element.element_type,
                source_entities=element.source_entities,
                source_layers=element.source_layers,
                calculation_basis=f"CAD detected sanitary fixture count = {int(count)}",
                status="MEASURED",
                confidence=element.confidence,
                rate=2200.0,
                amount=count * 2200.0,
            )
        )

    return quantities
