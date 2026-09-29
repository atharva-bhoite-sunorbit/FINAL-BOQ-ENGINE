from __future__ import annotations

from typing import Any
from backend.models.boq_item import BOQItem

# Chronological Construction Stages in sequence from site start to handover
CHRONOLOGICAL_SECTIONS = [
    "1. SUB-STRUCTURE & EARTHWORK",
    "2. PLAIN CEMENT CONCRETE (PCC)",
    "3. RCC SUB-STRUCTURE",
    "4. RCC SUPER-STRUCTURE",
    "5. REINFORCEMENT STEEL",
    "6. FORMWORK & SHUTTERING",
    "7. MASONRY & ENCLOSURE",
    "8. WATERPROOFING & DAMP PROOFING",
    "9. PLASTERING WORKS",
    "10. DOORS, WINDOWS & OPENINGS",
    "11. PARTITIONS & DRYWALLS",
    "12. FLOORING, TILING & SKIRTING",
    "13. CEILING WORKS",
    "14. PAINTING & SURFACE FINISHES",
    "15. METAL WORKS & RAILINGS",
    "16. PLUMBING & DRAINAGE",
    "17. SANITARY FIXTURES & CP FITTINGS",
    "18. ELECTRICAL & LOW VOLTAGE",
    "19. HVAC & VENTILATION",
    "20. EXTERNAL WORKS & SITE DEVELOPMENT",
]


def determine_section(element_type: str, material: str, description: str = "") -> str:
    """
    Maps an item to its chronological construction stage.
    """
    et = element_type.upper()
    mat = material.upper()
    desc = description.upper()
    comb = f"{et} {mat} {desc}"

    # 1. Earthwork
    if any(k in comb for k in ("EXCAVATION", "EARTHWORK", "BACKFILL", "TERMITE", "TRENCH")):
        return "1. SUB-STRUCTURE & EARTHWORK"

    # 2. PCC
    if any(k in comb for k in ("PCC", "PLAIN CEMENT CONCRETE", "LEVELLING COURSE", "M10", "M15")):
        return "2. PLAIN CEMENT CONCRETE (PCC)"

    # 5. Reinforcement Steel (takes priority for steel items)
    if "STEEL" in mat or "REBAR" in comb or "TMT" in comb or "FE 500" in comb or "STIRRUP" in comb:
        return "5. REINFORCEMENT STEEL"

    # 6. Formwork & Shuttering
    if any(k in comb for k in ("SHUTTERING", "FORMWORK", "CENTERING", "PROPS")):
        return "6. FORMWORK & SHUTTERING"

    # 3. RCC Substructure
    if any(k in et for k in ("FOOTING", "PILE", "FOUNDATION", "PLINTH_BEAM", "TIE_BEAM")):
        return "3. RCC SUB-STRUCTURE"

    # 4. RCC Superstructure
    if any(k in et for k in ("COLUMN", "BEAM", "SLAB", "SHEAR_WALL", "RETAINING_WALL", "LINTEL", "STAIRCASE", "RAMP")):
        return "4. RCC SUPER-STRUCTURE"

    # 8. Waterproofing
    if any(k in comb for k in ("WATERPROOF", "DPC", "COBA", "MEMBRANE", "UPTURN", "SEALANT", "SILICONE")):
        return "8. WATERPROOFING & DAMP PROOFING"

    # 7. Masonry
    if any(k in comb for k in ("BRICK", "AAC", "BLOCKWORK", "MASONRY", "SIPOREX")):
        return "7. MASONRY & ENCLOSURE"

    # 9. Plaster
    if "PLASTER" in comb:
        return "9. PLASTERING WORKS"

    # 10. Openings
    if any(k in et for k in ("DOOR", "WINDOW", "VENTILATOR", "GLAZING")):
        return "10. DOORS, WINDOWS & OPENINGS"

    # 11. Partitions
    if any(k in comb for k in ("PARTITION", "GYPSUM", "DRYWALL", "GLASS_PARTITION", "ALUMINIUM_PARTITION", "AEROCON")):
        return "11. PARTITIONS & DRYWALLS"

    # 12. Flooring
    if any(k in comb for k in ("FLOOR", "TILE", "VITRIFIED", "GRANITE", "MARBLE", "SKIRTING", "SCREED", "DADO")):
        return "12. FLOORING, TILING & SKIRTING"

    # 13. Ceiling
    if "CEILING" in comb or "FALSE CEILING" in comb or "POP" in comb:
        return "13. CEILING WORKS"

    # 14. Painting
    if any(k in comb for k in ("PAINT", "PUTTY", "PRIMER", "EMULSION", "ENAMEL")):
        return "14. PAINTING & SURFACE FINISHES"

    # 15. Metal Works
    if any(k in comb for k in ("RAILING", "HANDRAIL", "GRILL", "MS ", "SS ")):
        return "15. METAL WORKS & RAILINGS"

    # 16. Plumbing
    if any(k in comb for k in ("PLUMB", "PIPE", "DRAIN", "SEWER", "SWR", "CPVC", "UPVC")):
        return "16. PLUMBING & DRAINAGE"

    # 17. Sanitary
    if any(k in comb for k in ("SANITARY", "WC", "TOILET", "BASIN", "SHOWER", "FAUCET", "COMMODE")):
        return "17. SANITARY FIXTURES & CP FITTINGS"

    # 18. Electrical
    if any(k in comb for k in ("ELECTRICAL", "CONDUIT", "CABLE", "WIRE", "LIGHT", "SWITCH", "SOCKET", "DB")):
        return "18. ELECTRICAL & LOW VOLTAGE"

    # 19. HVAC
    if any(k in comb for k in ("HVAC", "DUCT", "DIFFUSER", "GRILLE", "FCU", "VENTILATION")):
        return "19. HVAC & VENTILATION"

    # 20. External
    if any(k in comb for k in ("ROAD", "PAVER", "KERB", "COMPOUND", "FENCE", "DRAINAGE_CHANNEL", "EXTERNAL")):
        return "20. EXTERNAL WORKS & SITE DEVELOPMENT"

    return "4. RCC SUPER-STRUCTURE"


def _aggregate_section_items(sec_items: list[BOQItem]) -> list[BOQItem]:
    """
    Aggregates items with the same material and unit within a section so each work item appears only once.
    """
    groups: dict[tuple[str, str], list[BOQItem]] = {}
    for item in sec_items:
        mat_key = item.material.strip().upper() if item.material else "GENERAL"
        unit_key = item.unit.strip().lower() if item.unit else ""
        key = (mat_key, unit_key)
        groups.setdefault(key, []).append(item)

    aggregated: list[BOQItem] = []
    for (mat_key, unit_key), group in groups.items():
        if len(group) == 1:
            aggregated.append(group[0])
            continue

        first = group[0]
        gross_total = round(sum(it.gross_quantity for it in group), 4)
        ded_total = round(sum(it.deduction_quantity for it in group), 4)
        net_total = round(sum(it.net_quantity for it in group), 4)
        wastage_qty_total = round(sum(it.wastage_quantity for it in group), 4)

        has_rebar_required = any(
            it.status in {"NOT_AVAILABLE", "STRUCTURAL_REBAR_DATA_REQUIRED"}
            or (it.total_quantity == 0.0 and "STEEL" in first.section.upper())
            for it in group
        )

        if has_rebar_required and "STEEL" in first.section.upper():
            total_qty = 0.0
            status = "STRUCTURAL_REBAR_DATA_REQUIRED"
            amount = 0.0
            confidence = 0.0
        else:
            total_qty = round(sum(it.total_quantity for it in group), 4)
            status = "MEASURED" if any(it.status == "MEASURED" for it in group) else first.status
            amount = round(total_qty * first.rate, 2)
            confidence = round(sum(it.confidence for it in group) / len(group), 2)

        all_elem_ids = []
        seen_elem_ids = set()
        for it in group:
            for eid in it.source_element_ids:
                if eid and eid not in seen_elem_ids:
                    seen_elem_ids.add(eid)
                    all_elem_ids.append(eid)

        all_entities = []
        seen_entities = set()
        for it in group:
            for handle in it.source_entities:
                if handle and handle not in seen_entities:
                    seen_entities.add(handle)
                    all_entities.append(handle)

        all_layers = []
        seen_layers = set()
        for it in group:
            for l in it.source_layers:
                if l and l not in seen_layers:
                    seen_layers.add(l)
                    all_layers.append(l)

        calc_basis = f"Aggregated {net_total:.2f} {first.unit} across {len(all_elem_ids)} element(s): {', '.join(all_elem_ids[:4])}{'...' if len(all_elem_ids) > 4 else ''}"

        agg_item = BOQItem(
            item_no=first.item_no,
            section=first.section,
            element_type=first.element_type,
            material=first.material,
            description=first.description,
            unit=first.unit,
            gross_quantity=gross_total,
            deduction_quantity=ded_total,
            net_quantity=net_total,
            wastage_percent=first.wastage_percent,
            wastage_quantity=wastage_qty_total,
            total_quantity=total_qty,
            rate=first.rate,
            material_rate=first.material_rate,
            labour_rate=first.labour_rate,
            amount=amount,
            calculation_basis=calc_basis,
            source_entities=all_entities,
            source_layers=all_layers,
            source_element_ids=all_elem_ids,
            status=status,
            confidence=confidence,
            remarks=first.remarks,
            specification=first.specification,
        )
        aggregated.append(agg_item)

    return aggregated


def group_boq_items(items: list[BOQItem], aggregate: bool = True) -> dict[str, list[BOQItem]]:
    """
    Groups items by their chronological construction section.
    Aggregates items within each section so each work item appears only once.
    Preserves stage order strictly.
    """
    grouped: dict[str, list[BOQItem]] = {sec: [] for sec in CHRONOLOGICAL_SECTIONS}
    for item in items:
        sec = item.section if item.section in grouped else determine_section(item.element_type, item.material, item.description)
        item.section = sec
        grouped.setdefault(sec, []).append(item)

    if aggregate:
        for sec, sec_items in grouped.items():
            if sec_items:
                grouped[sec] = _aggregate_section_items(sec_items)

    # Filter out empty sections but maintain sequence
    return {k: v for k, v in grouped.items() if v}
