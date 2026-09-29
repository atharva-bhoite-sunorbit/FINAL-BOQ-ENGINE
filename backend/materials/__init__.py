from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity

from .concrete import calculate_concrete
from .steel import calculate_steel, bar_weight_per_meter
from .brick import calculate_brickwork
from .blockwork import calculate_blockwork
from .plaster import calculate_plaster
from .gypsum import calculate_gypsum
from .glass import calculate_glass
from .aluminium import calculate_aluminium
from .flooring import calculate_flooring
from .ceiling import calculate_ceiling
from .paint import calculate_paint
from .waterproofing import calculate_waterproofing
from .doors import calculate_doors
from .windows import calculate_windows
from .formwork import calculate_formwork
from .sealant import calculate_sealant
from .insulation import calculate_insulation
from .electrical import calculate_electrical
from .plumbing import calculate_plumbing
from .sanitary import calculate_sanitary

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class MaterialEngine:
    def __init__(self, rules_path: Optional[Path] = None):
        self.rules_path = rules_path or (DATA_DIR / "material_rules.json")
        self.rules: dict[str, Any] = {}
        if self.rules_path.exists():
            try:
                self.rules = json.loads(self.rules_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to load material rules: {e}")

    def calculate_materials_for_element(
        self,
        element: ConstructionElement,
        rate_overrides: Optional[dict[str, Any]] = None,
    ) -> list[MaterialQuantity]:
        """
        Maps a single construction element to its complete multi-component material system.
        """
        etype = element.element_type.upper()
        subtype = element.subtype.upper()
        results: list[MaterialQuantity] = []

        try:
            # 1. Structural RCC Elements (Concrete + Rebar Steel + Formwork)
            if etype in {"COLUMN", "BEAM", "SLAB", "FOOTING", "FOUNDATION", "SHEAR_WALL", "RETAINING_WALL", "LINTEL", "STAIRCASE"}:
                results.extend(calculate_concrete(element))
                results.extend(calculate_formwork(element))
                results.extend(calculate_steel(element))

            # 2. Masonry Walls (Bricks/Blocks + Mortar Cement + Sand)
            elif etype == "WALL":
                if "AAC" in subtype or "BLOCK" in subtype or "SIPOREX" in subtype:
                    results.extend(calculate_blockwork(element))
                else:
                    results.extend(calculate_brickwork(element))
                # Add wall plastering and paint takeoff
                results.extend(calculate_paint(element))

            # 3. Partitions
            elif etype in {"PARTITION", "DRYWALL", "GLASS_PARTITION", "ALUMINIUM_PARTITION"}:
                if "GYP" in subtype or "DRYWALL" in subtype or "AEROCON" in subtype or "BOARD" in subtype:
                    results.extend(calculate_gypsum(element))
                elif "GLASS" in subtype or "ALUM" in subtype:
                    results.extend(calculate_glass(element))
                    results.extend(calculate_aluminium(element))
                    results.extend(calculate_sealant(element))
                else:
                    results.extend(calculate_gypsum(element))

            # 4. Openings
            elif etype == "DOOR":
                results.extend(calculate_doors(element))
            elif etype == "WINDOW":
                results.extend(calculate_windows(element))

            # 5. Finishes
            elif etype in {"FLOOR", "ROOM"}:
                results.extend(calculate_flooring(element))
            elif etype == "CEILING":
                results.extend(calculate_ceiling(element))
            elif etype in {"ROOF", "PARAPET"}:
                results.extend(calculate_waterproofing(element))

            # 6. MEP
            elif etype == "ELECTRICAL":
                results.extend(calculate_electrical(element))
            elif etype == "PLUMBING":
                results.extend(calculate_plumbing(element))
            elif etype == "SANITARY":
                results.extend(calculate_sanitary(element))

            # Fallback for other identified elements
            else:
                if element.geometry.get("area", 0) > 0:
                    results.extend(calculate_paint(element))

        except Exception as exc:
            logger.error(f"Error calculating materials for element {element.element_id}: {exc}")

        # Apply custom rate overrides if provided
        if rate_overrides:
            for item in results:
                if item.material_code in rate_overrides:
                    ov = rate_overrides[item.material_code]
                    new_rate = float(ov.get("rate", ov) if isinstance(ov, dict) else ov)
                    item.rate = new_rate
                    item.amount = round(item.total_quantity * new_rate, 2)

        return results

    def calculate_all(
        self,
        elements: list[ConstructionElement],
        rate_overrides: Optional[dict[str, Any]] = None,
        aggregate: bool = True,
    ) -> list[MaterialQuantity]:
        all_materials: list[MaterialQuantity] = []
        for elem in elements:
            all_materials.extend(self.calculate_materials_for_element(elem, rate_overrides))
        if aggregate:
            return aggregate_materials(all_materials)
        return all_materials


def aggregate_materials(materials: list[MaterialQuantity]) -> list[MaterialQuantity]:
    """
    Aggregates duplicate materials across elements so each unique material appears only once.
    """
    groups: dict[tuple[str, str], list[MaterialQuantity]] = {}
    for m in materials:
        key = (m.material_name.strip().upper(), m.unit.strip().lower())
        groups.setdefault(key, []).append(m)

    results: list[MaterialQuantity] = []
    for (mat_name_upper, unit_lower), group in groups.items():
        if len(group) == 1:
            results.append(group[0])
            continue

        first = group[0]
        net_total = round(sum(m.net_quantity for m in group), 4)
        wastage_total = round(sum(m.wastage_quantity for m in group), 4)

        has_rebar_required = any(
            m.status in {"NOT_AVAILABLE", "STRUCTURAL_REBAR_DATA_REQUIRED"}
            or (m.total_quantity == 0.0 and "REBAR" in m.material_code.upper())
            for m in group
        )

        if has_rebar_required and "STEEL" in first.category.upper():
            total_qty = 0.0
            status = "STRUCTURAL_REBAR_DATA_REQUIRED"
            amount = 0.0
            confidence = 0.0
        else:
            total_qty = round(sum(m.total_quantity for m in group), 4)
            status = "MEASURED" if any(m.status == "MEASURED" for m in group) else first.status
            amount = round(total_qty * first.rate, 2)
            confidence = round(sum(m.confidence for m in group) / len(group), 2)

        all_elem_ids = []
        seen_elem_ids = set()
        breakdown_by_type: dict[str, float] = {}
        for m in group:
            if m.source_element_id and m.source_element_id not in seen_elem_ids:
                seen_elem_ids.add(m.source_element_id)
                all_elem_ids.append(m.source_element_id)
            etype = (m.source_element_type or "other").lower() + "s"
            breakdown_by_type[etype] = round(breakdown_by_type.get(etype, 0.0) + m.net_quantity, 4)

        all_entities = []
        seen_entities = set()
        for m in group:
            for h in m.source_entities:
                if h and h not in seen_entities:
                    seen_entities.add(h)
                    all_entities.append(h)

        all_layers = []
        seen_layers = set()
        for m in group:
            for l in m.source_layers:
                if l and l not in seen_layers:
                    seen_layers.add(l)
                    all_layers.append(l)

        calc_basis = f"Aggregated {net_total:.2f} {first.unit} across {len(all_elem_ids)} element(s): {', '.join(all_elem_ids[:4])}{'...' if len(all_elem_ids) > 4 else ''}"

        agg_mat = MaterialQuantity(
            material_code=first.material_code,
            material_name=first.material_name,
            category=first.category,
            unit=first.unit,
            net_quantity=net_total,
            wastage_percent=first.wastage_percent,
            wastage_quantity=wastage_total,
            total_quantity=total_qty,
            source_element_id=", ".join(all_elem_ids[:5]),
            source_element_type=first.source_element_type,
            source_entities=all_entities,
            source_layers=all_layers,
            calculation_basis=calc_basis,
            status=status,
            confidence=confidence,
            rate=first.rate,
            amount=amount,
            remarks=first.remarks,
            element_breakdown=breakdown_by_type,
        )
        results.append(agg_mat)

    return results


__all__ = [
    "MaterialEngine",
    "calculate_concrete",
    "calculate_steel",
    "calculate_brickwork",
    "calculate_blockwork",
    "calculate_plaster",
    "calculate_gypsum",
    "calculate_glass",
    "calculate_aluminium",
    "calculate_flooring",
    "calculate_ceiling",
    "calculate_paint",
    "calculate_waterproofing",
    "calculate_doors",
    "calculate_windows",
    "calculate_formwork",
    "calculate_sealant",
    "calculate_insulation",
    "calculate_electrical",
    "calculate_plumbing",
    "calculate_sanitary",
]
