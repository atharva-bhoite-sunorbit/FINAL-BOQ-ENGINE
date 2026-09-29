from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent / "data"
MATERIAL_RULES_PATH = DATA_DIR / "material_rules.json"


def load_material_rules() -> dict[str, Any]:
    if MATERIAL_RULES_PATH.exists():
        try:
            return json.loads(MATERIAL_RULES_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load material rules: {e}")
    return {}


def bar_weight_per_meter(diameter_mm: float) -> float:
    """Standard structural formula: D^2 / 162 kg/m (IS 1786)."""
    return (diameter_mm ** 2) / 162.0


def map_quantities_to_materials(
    quantities: list[dict[str, Any]],
    rules: Optional[dict[str, Any]] = None,
    annotations: Optional[list[str]] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Maps geometric quantities to multi-component material systems (Section 22).
    Strictly applies Section 23 (Steel Quantity: no fabrication without structural rebar data).
    Aggregates all elements by material with detailed breakdown (Section 24).
    """
    if rules is None:
        rules = load_material_rules()

    material_items: list[dict[str, Any]] = []
    annots = [a.upper() for a in (annotations or [])]

    for q in quantities:
        etype = q.get("element_type", "").upper()
        elem_id = q.get("source_elements", ["GEN"])[0]
        net_qty = float(q.get("net_quantity", q.get("quantity", 0.0)))
        status = q.get("status", "MEASURED")

        # -------------------------------------------------------------
        # WALL → Masonry, Mortar, Plaster
        # -------------------------------------------------------------
        if etype == "WALL":
            subtype = str(q.get("subtype", "")).upper()
            if "AAC" in subtype or "BLOCK" in subtype:
                # AAC blocks (0.6 x 0.2 x 0.15 = 0.018 m3 per block -> ~55.5 blocks/m3)
                block_qty = round(net_qty * 55.55, 1)
                material_items.append({
                    "material_id": f"MAT-AAC-{elem_id}",
                    "material": "AAC Lightweight Blocks",
                    "category": "Masonry",
                    "unit": "nos",
                    "quantity": block_qty,
                    "wastage_percent": 3.0,
                    "total_quantity": round(block_qty * 1.03, 1),
                    "source_element": elem_id,
                    "element_type": "WALL",
                    "calculation_basis": f"55.55 blocks/m3 × {net_qty:.2f} m3 wall volume",
                    "status": status,
                    "source_entities": q.get("source_entities", []),
                })
            else:
                # Clay bricks: 500 bricks per m3 (IS 2212)
                brick_qty = round(net_qty * 500.0, 0)
                material_items.append({
                    "material_id": f"MAT-BRK-{elem_id}",
                    "material": "Standard Clay Bricks (Class 7.5)",
                    "category": "Masonry",
                    "unit": "nos",
                    "quantity": brick_qty,
                    "wastage_percent": 5.0,
                    "total_quantity": round(brick_qty * 1.05, 0),
                    "source_element": elem_id,
                    "element_type": "WALL",
                    "calculation_basis": f"500 bricks/m3 × {net_qty:.2f} m3 wall volume (IS 2212)",
                    "status": status,
                    "source_entities": q.get("source_entities", []),
                })

            # Mortar: ~0.25 m3 mortar per m3 masonry (1:6 cement:sand -> 1.34 bags cement, 0.28 m3 sand)
            cement_bags = round(net_qty * 1.34, 2)
            sand_cum = round(net_qty * 0.28, 2)
            material_items.append({
                "material_id": f"MAT-CMT-{elem_id}",
                "material": "OPC 43 Grade Cement",
                "category": "Cement & Mortar",
                "unit": "bags",
                "quantity": cement_bags,
                "wastage_percent": 2.5,
                "total_quantity": round(cement_bags * 1.025, 2),
                "source_element": elem_id,
                "element_type": "WALL",
                "calculation_basis": f"1.34 bags cement per m3 masonry for 1:6 mortar × {net_qty:.2f} m3",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })
            material_items.append({
                "material_id": f"MAT-SND-{elem_id}",
                "material": "Coarse Sand (Zone II)",
                "category": "Aggregates",
                "unit": "m3",
                "quantity": sand_cum,
                "wastage_percent": 5.0,
                "total_quantity": round(sand_cum * 1.05, 2),
                "source_element": elem_id,
                "element_type": "WALL",
                "calculation_basis": f"0.28 m3 sand per m3 masonry × {net_qty:.2f} m3",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })

            # Plaster (12mm internal plaster, 2 faces)
            # Surface area = 2 * length * height ≈ 2 * (volume / thickness)
            thickness = float(q.get("thickness", 0.23)) if q.get("thickness") else 0.23
            surf_area = round(2.0 * (net_qty / thickness), 2)
            material_items.append({
                "material_id": f"MAT-PLS-{elem_id}",
                "material": "Cement Plaster 12mm thick (1:4 mix)",
                "category": "Finishes",
                "unit": "m2",
                "quantity": surf_area,
                "wastage_percent": 2.5,
                "total_quantity": round(surf_area * 1.025, 2),
                "source_element": elem_id,
                "element_type": "WALL",
                "calculation_basis": f"2 faces × {net_qty:.2f}m3 / {thickness:.2f}m thickness",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })

        # -------------------------------------------------------------
        # COLUMN → Concrete, Formwork, Reinforcement Steel
        # -------------------------------------------------------------
        elif etype == "COLUMN":
            # Concrete
            material_items.append({
                "material_id": f"MAT-CONC-{elem_id}",
                "material": "Ready-Mix Concrete M25",
                "category": "Concrete",
                "unit": "m3",
                "quantity": net_qty,
                "wastage_percent": 2.5,
                "total_quantity": round(net_qty * 1.025, 3),
                "source_element": elem_id,
                "element_type": "COLUMN",
                "calculation_basis": f"Concrete Volume: {net_qty:.3f} m3",
                "status": status,
                "source_entities": q.get("source_entities", []),
            })

            # Formwork (shuttering): perimeter * height = 2*(w+d)*h
            # If w=0.3, d=0.45, h=3.0 -> 2*(0.75)*3 = 4.5 m2
            formwork_m2 = round(net_qty * 10.0, 2)  # typical formwork ratio for rectangular columns
            material_items.append({
                "material_id": f"MAT-FRM-{elem_id}",
                "material": "Steel / Plywood Shuttering Formwork",
                "category": "Formwork",
                "unit": "m2",
                "quantity": formwork_m2,
                "wastage_percent": 0.0,
                "total_quantity": formwork_m2,
                "source_element": elem_id,
                "element_type": "COLUMN",
                "calculation_basis": f"Contact formwork area for column {elem_id}",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })

            # Section 23: Strict Steel Quantity Rule
            steel_rec = _calculate_or_require_steel(elem_id, "COLUMN", net_qty, annots, q.get("source_entities", []))
            material_items.append(steel_rec)

        # -------------------------------------------------------------
        # BEAM → Concrete, Formwork, Reinforcement Steel
        # -------------------------------------------------------------
        elif etype == "BEAM":
            material_items.append({
                "material_id": f"MAT-CONC-{elem_id}",
                "material": "Ready-Mix Concrete M25",
                "category": "Concrete",
                "unit": "m3",
                "quantity": net_qty,
                "wastage_percent": 2.5,
                "total_quantity": round(net_qty * 1.025, 3),
                "source_element": elem_id,
                "element_type": "BEAM",
                "calculation_basis": f"Concrete Volume: {net_qty:.3f} m3",
                "status": status,
                "source_entities": q.get("source_entities", []),
            })
            formwork_m2 = round(net_qty * 8.5, 2)
            material_items.append({
                "material_id": f"MAT-FRM-{elem_id}",
                "material": "Steel / Plywood Shuttering Formwork",
                "category": "Formwork",
                "unit": "m2",
                "quantity": formwork_m2,
                "wastage_percent": 0.0,
                "total_quantity": formwork_m2,
                "source_element": elem_id,
                "element_type": "BEAM",
                "calculation_basis": f"Side and soffit formwork for beam {elem_id}",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })
            steel_rec = _calculate_or_require_steel(elem_id, "BEAM", net_qty, annots, q.get("source_entities", []))
            material_items.append(steel_rec)

        # -------------------------------------------------------------
        # SLAB → Concrete, Formwork, Reinforcement Steel
        # -------------------------------------------------------------
        elif etype == "SLAB":
            material_items.append({
                "material_id": f"MAT-CONC-{elem_id}",
                "material": "Ready-Mix Concrete M25",
                "category": "Concrete",
                "unit": "m3",
                "quantity": net_qty,
                "wastage_percent": 2.5,
                "total_quantity": round(net_qty * 1.025, 3),
                "source_element": elem_id,
                "element_type": "SLAB",
                "calculation_basis": f"Slab Concrete Volume: {net_qty:.3f} m3",
                "status": status,
                "source_entities": q.get("source_entities", []),
            })
            plan_area = float(q.get("plan_area_m2", net_qty / 0.15))
            material_items.append({
                "material_id": f"MAT-FRM-{elem_id}",
                "material": "Centering & Staging Formwork",
                "category": "Formwork",
                "unit": "m2",
                "quantity": round(plan_area, 2),
                "wastage_percent": 0.0,
                "total_quantity": round(plan_area, 2),
                "source_element": elem_id,
                "element_type": "SLAB",
                "calculation_basis": f"Soffit centering area: {plan_area:.2f} m2",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })
            steel_rec = _calculate_or_require_steel(elem_id, "SLAB", net_qty, annots, q.get("source_entities", []))
            material_items.append(steel_rec)

        # -------------------------------------------------------------
        # WINDOW → Aluminium/Frame, Glass, Sealant, Accessories
        # -------------------------------------------------------------
        elif etype == "WINDOW":
            area = net_qty
            # Glass
            material_items.append({
                "material_id": f"MAT-GLS-{elem_id}",
                "material": "Float Glass 6mm Toughened",
                "category": "Glass & Glazing",
                "unit": "m2",
                "quantity": area,
                "wastage_percent": 3.0,
                "total_quantity": round(area * 1.03, 2),
                "source_element": elem_id,
                "element_type": "WINDOW",
                "calculation_basis": f"Glazing window pane area: {area:.2f} m2",
                "status": status,
                "source_entities": q.get("source_entities", []),
            })
            # Aluminium frame profile: ~4.5 kg per m2 of window
            alu_kg = round(area * 4.5, 2)
            material_items.append({
                "material_id": f"MAT-ALU-{elem_id}",
                "material": "Extruded Aluminium Section (Powder Coated)",
                "category": "Aluminium",
                "unit": "kg",
                "quantity": alu_kg,
                "wastage_percent": 5.0,
                "total_quantity": round(alu_kg * 1.05, 2),
                "source_element": elem_id,
                "element_type": "WINDOW",
                "calculation_basis": f"4.5 kg/m2 frame profile × {area:.2f} m2",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })
            # Silicone Sealant
            sealant_rmt = round(area * 3.5, 1)
            material_items.append({
                "material_id": f"MAT-SEA-{elem_id}",
                "material": "Structural Silicone Weather Sealant",
                "category": "Sealants",
                "unit": "rmt",
                "quantity": sealant_rmt,
                "wastage_percent": 5.0,
                "total_quantity": round(sealant_rmt * 1.05, 1),
                "source_element": elem_id,
                "element_type": "WINDOW",
                "calculation_basis": f"Perimeter perimeter sealing: {sealant_rmt:.1f} rmt",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })

        # -------------------------------------------------------------
        # DOOR → Shutter, Frame, Hardware
        # -------------------------------------------------------------
        elif etype == "DOOR":
            count = net_qty
            material_items.append({
                "material_id": f"MAT-SHT-{elem_id}",
                "material": "Flush Door Shutter 35mm Solid Core",
                "category": "Doors & Joinery",
                "unit": "nos",
                "quantity": count,
                "wastage_percent": 0.0,
                "total_quantity": count,
                "source_element": elem_id,
                "element_type": "DOOR",
                "calculation_basis": f"Door leaf count: {count} nos",
                "status": status,
                "source_entities": q.get("source_entities", []),
            })
            material_items.append({
                "material_id": f"MAT-FRM-{elem_id}",
                "material": "Hardwood / Metal Door Frame Chowkhat",
                "category": "Doors & Joinery",
                "unit": "nos",
                "quantity": count,
                "wastage_percent": 0.0,
                "total_quantity": count,
                "source_element": elem_id,
                "element_type": "DOOR",
                "calculation_basis": f"Chowkhat frame count: {count} nos",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })
            material_items.append({
                "material_id": f"MAT-HDW-{elem_id}",
                "material": "Stainless Steel Door Hardware & Locksets",
                "category": "Hardware & Fixtures",
                "unit": "sets",
                "quantity": count,
                "wastage_percent": 0.0,
                "total_quantity": count,
                "source_element": elem_id,
                "element_type": "DOOR",
                "calculation_basis": f"Architectural hardware set per door: {count} sets",
                "status": "DERIVED",
                "source_entities": q.get("source_entities", []),
            })

        # -------------------------------------------------------------
        # FLOOR → Tiles, Mortar Bed, Skirting
        # -------------------------------------------------------------
        elif etype == "FLOOR":
            area = net_qty
            material_items.append({
                "material_id": f"MAT-TIL-{elem_id}",
                "material": "Vitrified Tiles (600x600mm)",
                "category": "Flooring & Tiling",
                "unit": "m2",
                "quantity": area,
                "wastage_percent": 5.0,
                "total_quantity": round(area * 1.05, 2),
                "source_element": elem_id,
                "element_type": "FLOOR",
                "calculation_basis": f"Floor area: {area:.2f} m2",
                "status": status,
                "source_entities": q.get("source_entities", []),
            })

    # Section 24: Aggregate materials with breakdown by element
    aggregated = aggregate_materials(material_items)
    return aggregated, aggregated


def _calculate_or_require_steel(
    elem_id: str,
    elem_type: str,
    concrete_vol_m3: float,
    annotations: list[str],
    source_entities: list[str],
) -> dict[str, Any]:
    """
    Section 23: Strict Reinforcement Steel Rule.
    If structural rebar information is absent, returns:
    {"steel_quantity": null, "status": "STRUCTURAL_REBAR_DATA_REQUIRED"}
    Never fabricates steel quantities.
    """
    rebar_found = False
    dia = 16.0
    bar_count = 8
    length = 3.0

    import re
    for annot in annotations:
        m = re.search(r"(\d+)\s*[TY#]\s*(\d+)", annot)
        if m:
            bar_count = int(m.group(1))
            dia = float(m.group(2))
            rebar_found = True
            break

    if not rebar_found:
        return {
            "material_id": f"MAT-STL-{elem_id}",
            "material": "Thermo-Mechanically Treated (TMT Fe 500D) Reinforcement Steel Bars",
            "category": "Reinforcement Steel",
            "steel_quantity": None,
            "status": "STRUCTURAL_REBAR_DATA_REQUIRED",
            "unit": "kg",
            "quantity": None,
            "wastage_percent": 3.0,
            "total_quantity": None,
            "source_element": elem_id,
            "element_type": elem_type,
            "calculation_basis": "Structural reinforcement schedule absent in CAD; status strictly marked STRUCTURAL_REBAR_DATA_REQUIRED per Section 23.",
            "source_entities": source_entities,
            "remarks": "Rebar schedule required from structural drawings.",
        }

    # If rebar information was explicitly found in annotations
    wt_per_m = bar_weight_per_meter(dia)
    eff_length = length + 50 * (dia / 1000.0)  # development length 50d
    total_wt = round(bar_count * eff_length * wt_per_m, 2)

    return {
        "material_id": f"MAT-STL-{elem_id}",
        "material": "Thermo-Mechanically Treated (TMT Fe 500D) Reinforcement Steel Bars",
        "category": "Reinforcement Steel",
        "steel_quantity": total_wt,
        "status": "MEASURED",
        "unit": "kg",
        "quantity": total_wt,
        "wastage_percent": 3.0,
        "total_quantity": round(total_wt * 1.03, 2),
        "source_element": elem_id,
        "element_type": elem_type,
        "calculation_basis": f"{bar_count} nos T{int(dia)} bars × {eff_length:.2f}m @ {wt_per_m:.3f} kg/m",
        "source_entities": source_entities,
        "remarks": f"Extracted from structural annotation: {bar_count}T{int(dia)}",
    }


def aggregate_materials(material_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Section 24: Aggregate all elements by material so each material appears only once.
    Returns:
    {
      "material": "Ready-Mix Concrete M25",
      "quantity": 520,
      "unit": "m3",
      "breakdown": {
        "slabs": 320,
        "columns": 110,
        "beams": 90
      }
    }
    """
    groups: dict[str, dict[str, Any]] = {}

    for item in material_items:
        mat_name = item.get("material", "Unknown")
        qty = item.get("quantity")
        total_q = item.get("total_quantity")
        unit = item.get("unit", "")
        etype = item.get("element_type", "OTHER").lower() + "s"
        rate = float(item.get("rate", item.get("unit_rate", 0.0)))

        if mat_name not in groups:
            groups[mat_name] = {
                "material_id": item.get("material_id", f"MAT-{mat_name}"),
                "material": mat_name,
                "material_name": mat_name,
                "category": item.get("category", "General"),
                "element_type": item.get("element_type", "MULTI"),
                "quantity": 0.0,
                "net_quantity": 0.0,
                "total_quantity": 0.0,
                "wastage_percent": item.get("wastage_percent", 0.0),
                "unit": unit,
                "rate": rate,
                "unit_rate": rate,
                "amount": 0.0,
                "breakdown": {},
                "element_breakdown": {},
                "source_elements": [],
                "source_entities": [],
                "has_null": False,
                "status": item.get("status", "MEASURED"),
            }

        g = groups[mat_name]

        src_elem = item.get("source_element")
        if src_elem and src_elem not in g["source_elements"]:
            g["source_elements"].append(src_elem)

        for h in item.get("source_entities", []):
            if h and h not in g["source_entities"]:
                g["source_entities"].append(h)

        if qty is None or item.get("status") == "STRUCTURAL_REBAR_DATA_REQUIRED":
            g["has_null"] = True
            g["status"] = "STRUCTURAL_REBAR_DATA_REQUIRED"
            g["breakdown"][etype] = "STRUCTURAL_REBAR_DATA_REQUIRED"
            g["element_breakdown"][etype] = "STRUCTURAL_REBAR_DATA_REQUIRED"
        else:
            q_val = float(qty)
            tq_val = float(total_q) if total_q is not None else q_val
            g["quantity"] = round(g["quantity"] + q_val, 3)
            g["net_quantity"] = g["quantity"]
            g["total_quantity"] = round(g["total_quantity"] + tq_val, 3)
            g["breakdown"][etype] = round(
                float(g["breakdown"].get(etype, 0.0)) + q_val, 3
            )
            g["element_breakdown"][etype] = g["breakdown"][etype]

    results = []
    for g in groups.values():
        is_null = g["has_null"] and g["quantity"] == 0.0
        final_qty = None if is_null else g["total_quantity"]
        net_qty = None if is_null else g["quantity"]
        amt = 0.0 if final_qty is None else round(final_qty * g["rate"], 2)

        res = {
            "material_id": g["material_id"],
            "material": g["material"],
            "material_name": g["material"],
            "category": g["category"],
            "element_type": g["element_type"],
            "steel_quantity": None if (g["category"] == "Reinforcement Steel" and is_null) else (final_qty if g["category"] == "Reinforcement Steel" else None),
            "quantity": net_qty,
            "net_quantity": net_qty,
            "wastage_percent": g["wastage_percent"],
            "total_quantity": final_qty,
            "unit": g["unit"],
            "rate": g["rate"],
            "unit_rate": g["rate"],
            "amount": amt,
            "total_cost": amt,
            "breakdown": g["breakdown"],
            "element_breakdown": g["element_breakdown"],
            "source_elements": g["source_elements"],
            "source_entities": g["source_entities"],
            "status": g["status"],
            "calculation_basis": (
                f"Aggregated total: {net_qty} {g['unit']} across {len(g['source_elements'])} element(s)"
                if net_qty is not None
                else "STRUCTURAL_REBAR_DATA_REQUIRED"
            ),
        }
        results.append(res)

    return results


# Backward compatibility for legacy tests
def calculate_materials(items: list[dict[str, Any]], rules: dict[str, Any]) -> dict[str, Any]:
    mapped, aggregated = map_quantities_to_materials(items, rules)
    return {
        "items": mapped,
        "summary": aggregated,
    }
