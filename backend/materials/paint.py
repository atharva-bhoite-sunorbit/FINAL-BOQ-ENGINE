from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_paint(
    element: ConstructionElement,
    coats: int = 2,
    is_exterior: bool = False,
) -> list[MaterialQuantity]:
    """
    Calculates painting system materials:
    - Wall Putty (2 coats): 1.4 kg / sqm
    - Wall Primer (1 coat): 0.08 litres / sqm
    - Emulsion Paint (2 coats): 0.16 litres / sqm
    """
    area = float(element.geometry.get("area", 0.0))
    if area <= 0:
        length = float(element.geometry.get("length", 0.0))
        height = float(element.geometry.get("height", 3.0))
        area = length * height * (1.0 if is_exterior else 2.0)

    if area <= 0:
        return []

    results: list[MaterialQuantity] = []

    # 1. Acrylic Wall Putty
    putty_kg = area * 1.40
    results.append(
        MaterialQuantity(
            material_id=f"MAT-PTY-{element.element_id}",
            material_name="White Cement Based Acrylic Wall Putty (2 Coats)",
            category="Paints & Chemicals",
            unit="kg",
            quantity=round(putty_kg, 1),
            wastage_percent=3.0,
            total_quantity=round(putty_kg * 1.03, 1),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Surface {area:.2f} sqm x 1.4 kg/sqm",
            status=element.status,
            confidence=element.confidence,
            rate=28.0,
            amount=round(putty_kg * 1.03 * 28.0, 2),
        )
    )

    # 2. Water-thinnable Primer
    primer_litres = area * 0.08
    results.append(
        MaterialQuantity(
            material_id=f"MAT-PRM-{element.element_id}",
            material_name="Water Thinnable Exterior/Interior Wall Primer (1 Coat)",
            category="Paints & Chemicals",
            unit="litres",
            quantity=round(primer_litres, 2),
            wastage_percent=3.0,
            total_quantity=round(primer_litres * 1.03, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Surface {area:.2f} sqm x 0.08 L/sqm",
            status=element.status,
            confidence=element.confidence,
            rate=160.0,
            amount=round(primer_litres * 1.03 * 160.0, 2),
        )
    )

    # 3. Premium Emulsion Paint
    paint_litres = area * 0.16
    paint_name = "Premium Exterior Weatherproof Emulsion Paint (2 Coats)" if is_exterior else "Premium Luxury Interior Acrylic Emulsion Paint (2 Coats)"
    rate = 380.0 if is_exterior else 320.0

    results.append(
        MaterialQuantity(
            material_id=f"MAT-PNT-{element.element_id}",
            material_name=paint_name,
            category="Paints & Chemicals",
            unit="litres",
            quantity=round(paint_litres, 2),
            wastage_percent=3.0,
            total_quantity=round(paint_litres * 1.03, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Surface {area:.2f} sqm x 0.16 L/sqm (2 coats)",
            status=element.status,
            confidence=element.confidence,
            rate=rate,
            amount=round(paint_litres * 1.03 * rate, 2),
        )
    )

    return results
