from __future__ import annotations

from typing import Dict, Any


REFERENCE_RATES = {
    "GLP-001": 300, "AEP-002": 220, "VFT-003": 148, "GYP-004": 225,
    "PLY-005": 320, "MGP-006": 240, "PNT-007": 20, "DOR-008": 25,
    "AAC-009": 300, "PLS-010": 220, "CPL-011": 148, "GPR-012": 225,
    "FCL-013": 320, "WTR-014": 240, "ROF-015": 220, "FIN-016": 20,
    "WSR-017": 25,
    "RCC-001": 300, "MAS-002": 220, "PLS-003": 148, "FLR-004": 225,
    "DOR-005": 320, "WIN-006": 240, "PLM-007": 20, "ELE-008": 25,
}


def _item(code, category, description, material, quantity, unit, wastage_pct, rates, parsed, confidence):
    quantity = round(quantity, 2)
    final_quantity = round(quantity * (1 + wastage_pct / 100), 2)
    rate = float(rates[code])
    return {
        "code": code,
        "category": category,
        "description": description,
        "material": material,
        "spec": "As per approved drawing/specification",
        "location": "All detected floors / locations",
        "quantity": quantity,
        "unit": unit,
        "wastage_pct": wastage_pct,
        "final_quantity": final_quantity,
        "rate": rate,
        "amount": round(final_quantity * rate, 2),
        "drawing_reference": parsed.get("file_name", "N/A"),
        "confidence": confidence,
        "remarks": "Rate and quantity are editable; verify against detailed drawing/specification.",
        "calculation": f"{quantity} {unit} + {wastage_pct}% wastage = {final_quantity} {unit}",
    }


def calculate_boq(parsed: Dict[str, Any], rate_overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    rates = {**REFERENCE_RATES, **(rate_overrides or {})}
    counts = parsed.get("counts", {})
    wall_count = max(1, counts.get("walls", 12))
    door_count = max(1, counts.get("doors", 6))
    window_count = max(1, counts.get("windows", 4))
    slab_count = max(1, counts.get("slabs", 2))
    plumbing_count = max(1, counts.get("plumbing", 3))
    electrical_count = max(1, counts.get("electrical", 12))

    wall_area = 245.0 * wall_count / 10
    plaster_area = 220.0 * wall_count / 10
    tile_area = 160.0 * wall_count / 10
    concrete_vol = 43.0 * slab_count
    plumbing_rmt = 26.0 * plumbing_count
    confidence = round(parsed.get("confidence", 0.8) * 100, 1)
    door_nos = door_count
    window_nos = window_count
    electrical_nos = electrical_count

    items = [
        _item("GLP-001", "Partitions", "Providing and fixing glass aluminium partition with powder-coated frame, approved glass, beading, sealant, accessories and installation complete.", "Glass aluminium partition", wall_count * 3.0, "sqft", 5, rates, parsed, confidence),
        _item("AEP-002", "Partitions", "Providing and fixing Aerocon partition including approved boards, GI framework, jointing compound, fasteners, cutting, wastage and finishing complete.", "Aerocon partition", wall_count * 2.5, "sqft", 5, rates, parsed, confidence),
        _item("VFT-003", "Flooring", "Providing and laying vitrified floor tiles with adhesive or cement mortar bed, cutting, spacers, grouting, curing, cleaning and finishing complete.", "Vitrified floor tiles", tile_area, "sqft", 5, rates, parsed, confidence),
        _item("GYP-004", "Partitions", "Providing and fixing gypsum board partition with GI framework, boards on both faces, joint treatment, screws, corner beads and finishing complete.", "Gypsum partition", wall_count * 2.5, "sqft", 5, rates, parsed, confidence),
        _item("PLY-005", "Partitions", "Providing and fixing plywood partition with approved plywood, framing, laminate or paint finish, edge treatment, hardware and accessories complete.", "Plywood partition", wall_count * 2.0, "sqft", 5, rates, parsed, confidence),
        _item("MGP-006", "Partitions", "Providing and fixing mixed gypsum partition including board types, GI framework, insulation where specified, jointing, access panels and finishing complete.", "Mixed gypsum", wall_count * 1.5, "sqft", 5, rates, parsed, confidence),
        _item("PNT-007", "Painting", "Providing and applying primer, putty and approved emulsion paint including surface preparation, sanding, two coats and touch-ups complete.", "Painting", plaster_area * 2, "sqft", 3, rates, parsed, confidence),
        _item("DOR-008", "Doors", "Providing and fixing doors including frame, shutter, hinges, handles, locks, door stopper, closer, polish or paint and hardware complete.", "Doors", door_count, "nos", 0, rates, parsed, confidence),
        _item("AAC-009", "Masonry", "Providing and constructing AAC/concrete block masonry in approved thickness with cement mortar, bonding, cutting, scaffolding, curing and joints complete.", "AAC/concrete", wall_count * 8.0, "sqft", 5, rates, parsed, confidence),
        _item("PLS-010", "Plaster", "Providing and applying plaster to internal and external masonry surfaces including preparation, corner beads, curing and smooth finish complete.", "Plaster", plaster_area, "sqft", 5, rates, parsed, confidence),
        _item("CPL-011", "Plaster", "Providing and applying cement plaster in specified thickness and mortar proportion to walls and soffits including scaffolding, curing and finishing complete.", "Cement plaster", plaster_area * 0.8, "sqft", 5, rates, parsed, confidence),
        _item("GPR-012", "Plaster", "Providing and applying gypsum plaster to approved internal surfaces including preparation, levelling, corner treatment and smooth finish complete.", "Gypsum plaster", plaster_area * 0.35, "sqft", 5, rates, parsed, confidence),
        _item("FCL-013", "False Ceiling", "Providing and fixing false ceiling with gypsum board or approved system, suspended framework, hangers, jointing, access panels and finishing complete.", "False ceiling", tile_area, "sqft", 5, rates, parsed, confidence),
        _item("WTR-014", "Water Tank", "Providing and installing water tank including tank body, platform or supports, inlet, outlet, overflow, drain, cover, connections and testing complete.", "Water tank", max(1, round(plumbing_count / 2)), "nos", 0, rates, parsed, confidence),
        _item("ROF-015", "Roofing", "Providing and fixing roofing system including sheets or tiles, supporting members, insulation where specified, flashing, ridge, gutters and sealants complete.", "Roofing", tile_area * 0.85, "sqft", 5, rates, parsed, confidence),
        _item("FIN-016", "Finishing", "Providing and completing architectural finishing works including substrate preparation, trims, sealants, touch-ups, cleaning and handover complete.", "Finishing", tile_area * 0.3, "sqft", 3, rates, parsed, confidence),
        _item("WSR-017", "Washroom", "Providing and completing washroom works including waterproofing, floor and wall tiles, sanitary fixtures, CP fittings, traps, accessories, testing and cleaning complete.", "Washroom", max(1, round(plumbing_count / 2)), "nos", 0, rates, parsed, confidence),
    ]
    legacy_items = [
        {
            "code": "RCC-001",
            "category": "RCC",
            "description": "Providing and casting RCC slab M25, 150 mm thick, including formwork, reinforcement placement, compaction, curing and finishing complete.",
            "material": "RCC M25",
            "spec": "150 mm thick",
            "location": "Ground Floor",
            "quantity": round(concrete_vol, 2),
            "unit": "m3",
            "wastage_pct": 2,
            "final_quantity": round(concrete_vol * 1.02, 2),
            "rate": rates["RCC-001"],
            "amount": round(concrete_vol * 1.02 * rates["RCC-001"], 2),
            "drawing_reference": parsed.get("file_name", "N/A"),
            "confidence": round(parsed.get("confidence", 0.8) * 100, 1),
            "remarks": "Derived from slab count and standard construction assumptions",
        },
        {
            "code": "MAS-002",
            "category": "Masonry",
            "description": "Constructing brick masonry wall 230 mm thick in cement mortar 1:6 including curing and joints.",
            "material": "Brick masonry",
            "spec": "230 mm thick",
            "location": "Ground Floor",
            "quantity": round(wall_area, 2),
            "unit": "m2",
            "wastage_pct": 5,
            "final_quantity": round(wall_area * 1.05, 2),
            "rate": rates["MAS-002"],
            "amount": round(wall_area * 1.05 * rates["MAS-002"], 2),
            "drawing_reference": parsed.get("file_name", "N/A"),
            "confidence": round(parsed.get("confidence", 0.8) * 100, 1),
            "remarks": "Quantity based on wall segments detected in drawing",
        },
        {
            "code": "PLS-003",
            "category": "Plaster",
            "description": "Internal cement plaster 12 mm thick on masonry surface, including preparation, curing and finishing.",
            "material": "Cement plaster",
            "spec": "12 mm",
            "location": "Ground Floor",
            "quantity": round(plaster_area, 2),
            "unit": "m2",
            "wastage_pct": 5,
            "final_quantity": round(plaster_area * 1.05, 2),
            "rate": rates["PLS-003"],
            "amount": round(plaster_area * 1.05 * rates["PLS-003"], 2),
            "drawing_reference": parsed.get("file_name", "N/A"),
            "confidence": round(parsed.get("confidence", 0.8) * 100, 1),
            "remarks": "Deduction for openings not computed in this demo; review with drawing details",
        },
        {
            "code": "FLR-004",
            "category": "Flooring",
            "description": "Providing and laying vitrified flooring tiles 600x600 mm with screed, adhesive and grouting complete.",
            "material": "Vitrified tiles",
            "spec": "600x600 mm",
            "location": "Ground Floor",
            "quantity": round(tile_area, 2),
            "unit": "m2",
            "wastage_pct": 5,
            "final_quantity": round(tile_area * 1.05, 2),
            "rate": rates["FLR-004"],
            "amount": round(tile_area * 1.05 * rates["FLR-004"], 2),
            "drawing_reference": parsed.get("file_name", "N/A"),
            "confidence": round(parsed.get("confidence", 0.8) * 100, 1),
            "remarks": "Tile quantity estimated from floor area and visible plan zones",
        },
        {
            "code": "DOR-005",
            "category": "Doors & Windows",
            "description": "Supply and installation of flush door 900x2100 mm with frame, hinges, handles and lockset.",
            "material": "Flush door",
            "spec": "900x2100 mm",
            "location": "Ground Floor",
            "quantity": door_nos,
            "unit": "nos",
            "wastage_pct": 0,
            "final_quantity": door_nos,
            "rate": rates["DOR-005"],
            "amount": round(door_nos * rates["DOR-005"], 2),
            "drawing_reference": parsed.get("file_name", "N/A"),
            "confidence": round(parsed.get("confidence", 0.8) * 100, 1),
            "remarks": "Door count based on drawing entity detection",
        },
        {
            "code": "WIN-006",
            "category": "Doors & Windows",
            "description": "Supply and fixing of aluminium glazed window 1500x1200 mm with frame and glass.",
            "material": "Aluminium window",
            "spec": "1500x1200 mm",
            "location": "Ground Floor",
            "quantity": window_nos,
            "unit": "nos",
            "wastage_pct": 0,
            "final_quantity": window_nos,
            "rate": rates["WIN-006"],
            "amount": round(window_nos * rates["WIN-006"], 2),
            "drawing_reference": parsed.get("file_name", "N/A"),
            "confidence": round(parsed.get("confidence", 0.8) * 100, 1),
            "remarks": "Window count estimated from opening tags and layers",
        },
        {
            "code": "PLM-007",
            "category": "Plumbing",
            "description": "Providing and fixing CPVC water supply pipeline 20 mm dia including fittings and support.",
            "material": "CPVC pipe",
            "spec": "20 mm dia",
            "location": "Ground Floor",
            "quantity": plumbing_rmt,
            "unit": "rmt",
            "wastage_pct": 5,
            "final_quantity": round(plumbing_rmt * 1.05, 2),
            "rate": rates["PLM-007"],
            "amount": round(plumbing_rmt * 1.05 * rates["PLM-007"], 2),
            "drawing_reference": parsed.get("file_name", "N/A"),
            "confidence": round(parsed.get("confidence", 0.8) * 100, 1),
            "remarks": "Routing should be confirmed on site for exact lengths",
        },
        {
            "code": "ELE-008",
            "category": "Electrical",
            "description": "Providing and fixing electrical light point with conduit and accessories complete.",
            "material": "LED light point",
            "spec": "Standard point",
            "location": "Ground Floor",
            "quantity": electrical_nos,
            "unit": "nos",
            "wastage_pct": 0,
            "final_quantity": electrical_nos,
            "rate": rates["ELE-008"],
            "amount": round(electrical_nos * rates["ELE-008"], 2),
            "drawing_reference": parsed.get("file_name", "N/A"),
            "confidence": round(parsed.get("confidence", 0.8) * 100, 1),
            "remarks": "Electrical load points estimated from detected fixtures",
        },
    ]
    items.extend(legacy_items)

    material_summary = {
        "RCC M25": round(concrete_vol * 1.02, 2),
        "Brick masonry": round(wall_area * 1.05, 2),
        "Cement plaster": round(plaster_area * 1.05, 2),
        "Vitrified tiles": round(tile_area * 1.05, 2),
        "CPVC pipe": round(plumbing_rmt * 1.05, 2),
    }

    subtotal = round(sum(item["amount"] for item in items), 2)
    material_cost = round(subtotal * 0.70, 2)
    labour_cost = round(subtotal * 0.30, 2)
    tax = round(subtotal * 0.05, 2)
    grand_total = round(subtotal + tax, 2)

    return {
        "items": items,
        "materials": material_summary,
        "cost": {
            "material_cost": material_cost,
            "labour_cost": labour_cost,
            "subtotal": subtotal,
            "tax": tax,
            "tax_rate": 5,
            "grand_total": grand_total,
        },
        "project": {
            "file_name": parsed.get("file_name", "N/A"),
            "units": parsed.get("units", "m"),
            "scale": parsed.get("scale", "1:100"),
            "floors": parsed.get("floors", ["Ground Floor"]),
        },
        "rates": rates,
    }
