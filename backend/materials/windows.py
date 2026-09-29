from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_windows(element: ConstructionElement, wastage_percent: float = 3.0) -> list[MaterialQuantity]:
    """
    Calculates window system materials:
    - Aluminium framing sections (kg / rm)
    - Glazing glass panes (m2)
    - EPDM weatherstrip gaskets & sealant (rm)
    - Hardware fittings (locks, handles, rollers) (set)
    """
    geo = element.geometry
    width = float(geo.get("width", 1.2) or 1.2)
    height = float(geo.get("height", 1.2) or 1.2)
    area = float(geo.get("area", 0.0) or (width * height))
    perimeter = 2 * (width + height)

    if area <= 0:
        return []

    quantities: list[MaterialQuantity] = []

    # 1. Glass Pane (5mm / 6mm Clear Float Glass)
    glass_wastage = 5.0
    tot_glass = area * (1 + glass_wastage / 100.0)
    quantities.append(
        MaterialQuantity(
            material_id=f"MAT-WIN-GLS-{element.element_id}",
            material_name="5mm Clear Toughened Window Glass Pane",
            category="Glass & Aluminium",
            unit="m2",
            quantity=round(area, 4),
            wastage_percent=glass_wastage,
            total_quantity=round(tot_glass, 4),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            source_entities=element.source_entities,
            source_layers=element.source_layers,
            calculation_basis=f"Window area {width:.2f}m x {height:.2f}m = {area:.2f} m2 + {glass_wastage}% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=1450.0,
            amount=round(tot_glass * 1450.0, 2),
        )
    )

    # 2. Aluminium Window Frame Section (3-track / 2-track powder coated)
    # Typical weight ~ 1.2 kg per rmt of perimeter run
    frame_weight = perimeter * 1.25
    tot_frame = frame_weight * (1 + wastage_percent / 100.0)
    quantities.append(
        MaterialQuantity(
            material_id=f"MAT-WIN-ALU-{element.element_id}",
            material_name="Powder Coated Aluminium Window Sections (Heavy Duty)",
            category="Glass & Aluminium",
            unit="kg",
            quantity=round(frame_weight, 3),
            wastage_percent=wastage_percent,
            total_quantity=round(tot_frame, 3),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            source_entities=element.source_entities,
            source_layers=element.source_layers,
            calculation_basis=f"Perimeter {perimeter:.2f}m x 1.25 kg/m = {frame_weight:.2f} kg",
            status=element.status,
            confidence=element.confidence,
            rate=380.0,
            amount=round(tot_frame * 380.0, 2),
        )
    )

    # 3. EPDM Gaskets & Weatherstrip
    gasket_len = perimeter * 2.0
    tot_gasket = gasket_len * (1 + wastage_percent / 100.0)
    quantities.append(
        MaterialQuantity(
            material_id=f"MAT-WIN-EPD-{element.element_id}",
            material_name="EPDM Weatherstrips & Neoprene Gaskets",
            category="Hardware & Sealants",
            unit="rm",
            quantity=round(gasket_len, 2),
            wastage_percent=wastage_percent,
            total_quantity=round(tot_gasket, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            source_entities=element.source_entities,
            source_layers=element.source_layers,
            calculation_basis=f"Double gasket run {perimeter:.2f}m x 2 = {gasket_len:.2f} rm",
            status=element.status,
            confidence=element.confidence,
            rate=35.0,
            amount=round(tot_gasket * 35.0, 2),
        )
    )

    # 4. Window Hardware & Fasteners
    quantities.append(
        MaterialQuantity(
            material_id=f"MAT-WIN-HDW-{element.element_id}",
            material_name="Window Hardware Pack (Bearings, SS Fasteners, Touch Locks)",
            category="Hardware & Fasteners",
            unit="set",
            quantity=1.0,
            wastage_percent=0.0,
            total_quantity=1.0,
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            source_entities=element.source_entities,
            source_layers=element.source_layers,
            calculation_basis="1 hardware set per window unit",
            status="MEASURED",
            confidence=0.95,
            rate=650.0,
            amount=650.0,
        )
    )

    return quantities
