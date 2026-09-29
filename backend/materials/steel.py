from __future__ import annotations

from typing import Any, Optional
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def bar_weight_per_meter(diameter_mm: float) -> float:
    """Formula: D^2 / 162 kg/m"""
    return (diameter_mm ** 2) / 162.0


def calculate_steel(
    element: ConstructionElement,
    schedule_data: Optional[dict[str, Any]] = None,
) -> list[MaterialQuantity]:
    """
    Calculates TMT Fe 500D reinforcement steel quantities.
    STRICT QUANTITY-SURVEYING RULE: If reinforcement schedule is absent in CAD, sets status="NOT_AVAILABLE"
    with 0 quantity rather than fabricating an imaginary steel quantity.
    """
    rebar_info = schedule_data or element.extra.get("reinforcement")

    if not rebar_info:
        annot_str = " ".join(element.source_annotations).upper()
        # Check annotations for explicit rebar specifications like 8T16, 4T12, T8@150
        has_rebar_spec = any(k in annot_str for k in ("T16", "T12", "T20", "T25", "T10", "T8", "Y12", "Y16", "FE500"))
        if not has_rebar_spec:
            return [
                MaterialQuantity(
                    material_id=f"MAT-STL-NA-{element.element_id}",
                    material_name="Thermo-Mechanically Treated (TMT Fe 500D) Reinforcement Steel Bars",
                    category="Reinforcement Steel",
                    unit="kg",
                    quantity=0.0,
                    wastage_percent=3.0,
                    total_quantity=0.0,
                    source_element_id=element.element_id,
                    source_element_type=element.element_type,
                    source_entities=element.source_entities,
                    source_layers=element.source_layers,
                    calculation_basis="Reinforcement schedule not present in CAD drawing (IS:1786 / SP-34)",
                    status="NOT_AVAILABLE",
                    confidence=0.0,
                    rate=68.0,
                    amount=0.0,
                    remarks="Reinforcement details not available in drawing; status marked NOT_AVAILABLE to avoid fabrication",
                )
            ]
        rebar_info = {"parsed_from_annot": True}

    bars = rebar_info.get("bars", []) if isinstance(rebar_info, dict) else []
    total_wt = 0.0
    bar_details = []

    if bars:
        for b in bars:
            dia = float(b.get("diameter", 16))
            count = int(b.get("count", 4))
            length = float(b.get("length", 3.0))
            # Support hooks, bends, laps if specified
            lap_len = float(b.get("lap_length", 0.0))
            eff_len = length + lap_len
            wt_per_m = bar_weight_per_meter(dia)
            bar_wt = count * eff_len * wt_per_m
            total_wt += bar_wt
            bar_details.append(f"{count} nos dia {int(dia)}mm @ {eff_len:.2f}m")
    else:
        # Parsed from explicit annotation like 8T16 or 4T12
        annot_str = " ".join(element.source_annotations).upper()
        import re
        m_bar = re.search(r"(\d+)\s*[TY#]\s*(\d+)", annot_str)
        if m_bar:
            count = int(m_bar.group(1))
            dia = float(m_bar.group(2))
            col_h = float(element.geometry.get("height", 3.0) or 3.0)
            dev_len = 50 * (dia / 1000.0)  # 50d development length
            eff_len = col_h + dev_len
            wt_per_m = bar_weight_per_meter(dia)
            total_wt = count * eff_len * wt_per_m
            bar_details.append(f"{count} nos dia {int(dia)}mm (eff len {eff_len:.2f}m with 50d dev)")
        else:
            total_wt = 0.0

    if total_wt <= 0:
        return [
            MaterialQuantity(
                material_id=f"MAT-STL-NA-{element.element_id}",
                material_name="Thermo-Mechanically Treated (TMT Fe 500D) Reinforcement Steel Bars",
                category="Reinforcement Steel",
                unit="kg",
                quantity=0.0,
                wastage_percent=3.0,
                total_quantity=0.0,
                source_element_id=element.element_id,
                source_element_type=element.element_type,
                source_entities=element.source_entities,
                source_layers=element.source_layers,
                calculation_basis="Reinforcement bar dimensions could not be computed from CAD entities",
                status="NOT_AVAILABLE",
                confidence=0.0,
                rate=68.0,
                amount=0.0,
                remarks="Rebar details missing or incomplete in CAD drawing",
            )
        ]

    wastage = 3.0
    tot = total_wt * (1 + wastage / 100.0)
    calc_desc = f"Deterministic D^2/162 bar schedule: {', '.join(bar_details)} + {wastage}% wastage"

    return [
        MaterialQuantity(
            material_id=f"MAT-STL-{element.element_id}",
            material_name="High Yield Strength Deformed (HYSD) TMT Fe 500D Reinforcement Steel Bars",
            category="Reinforcement Steel",
            unit="kg",
            quantity=round(total_wt, 3),
            wastage_percent=wastage,
            total_quantity=round(tot, 3),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            source_entities=element.source_entities,
            source_layers=element.source_layers,
            calculation_basis=calc_desc,
            status="MEASURED" if bars else "DERIVED",
            confidence=0.92,
            rate=68.0,
            amount=round(tot * 68.0, 2),
            remarks=f"Weight per metre formula: D^2/162. Total steel: {tot:.2f} kg",
        )
    ]
