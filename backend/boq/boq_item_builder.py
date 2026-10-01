from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from backend.models.boq_item import BOQItem
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity
from .boq_grouping import determine_section

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class BOQItemBuilder:
    def __init__(self, templates_path: Optional[Path] = None):
        self.templates_path = templates_path or (DATA_DIR / "boq_templates.json")
        self.templates: dict[str, str] = {}
        if self.templates_path.exists():
            try:
                self.templates = json.loads(self.templates_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def build_item_from_material(
        self,
        item_no: int,
        material: MaterialQuantity,
        element: Optional[ConstructionElement] = None,
        rates_db: Optional[dict[str, Any]] = None,
    ) -> BOQItem:
        element_type = material.source_element_type or (element.element_type if element else "GENERAL")
        description = self.generate_specification_description(material, element)
        section = determine_section(element_type, material.material_name, description)

        rate = material.rate
        if rate <= 0 and rates_db:
            rate_info = rates_db.get(material.material_code, {})
            rate = float(rate_info.get("material_rate", rate_info.get("rate", 0.0)))

        amount = round(material.total_quantity * rate, 2)

        source_entities = list(material.source_entities)
        source_layers = list(material.source_layers)
        if element:
            if not source_entities:
                source_entities = list(element.source_entities)
            if not source_layers:
                source_layers = list(element.source_layers)

        return BOQItem(
            item_no=item_no,
            section=section,
            element_type=element_type,
            material=material.material_name,
            description=description,
            unit=material.unit,
            gross_quantity=material.net_quantity,
            deduction_quantity=0.0,
            net_quantity=material.net_quantity,
            wastage_percent=material.wastage_percent,
            wastage_quantity=material.wastage_quantity,
            total_quantity=material.total_quantity,
            rate=rate,
            material_rate=rate,
            labour_rate=0.0,
            amount=amount,
            calculation_basis=material.calculation_basis,
            source_entities=source_entities,
            source_layers=source_layers,
            source_element_ids=[s.strip() for s in (material.source_element_id or "").split(",") if s.strip()] or ([element.element_id] if element else []),
            status=material.status,
            confidence=material.confidence,
            remarks=material.remarks,
            specification=description,
        )

    def generate_specification_description(
        self,
        material: MaterialQuantity,
        element: Optional[ConstructionElement] = None,
    ) -> str:
        code = material.material_code.upper()
        name = material.material_name.upper()

        # Check template overrides
        if material.material_code in self.templates:
            return self.templates[material.material_code]

        # 1. Formwork / Shuttering (must be evaluated before steel because shuttering contains 'steel props')
        if any(k in code for k in ("SHUT", "FRM")) or any(k in name for k in ("SHUTTERING", "FORMWORK", "CENTERING", "PROPS")):
            return (
                "Centering and shuttering with film-faced waterproof marine plywood shuttering plates, steel battens, "
                "adjustable steel telescopic props, bracing, staging, applying approved mould releasing oil, and dismantling complete."
            )

        # 2. Mortar / Thin Bed Adhesive
        if "MORTAR" in name or "ADHESIVE" in name:
            return (
                "Providing, mixing, and applying polymer-modified thin-bed jointing adhesive mortar "
                "conforming to IS:15477 / standard architectural specifications complete."
            )

        # 3. AAC Blockwork / Brickwork (must be evaluated before concrete because AAC contains 'Concrete')
        if any(k in code for k in ("BLK", "AAC")) or "AAC" in name or "BLOCK" in name:
            return (
                "Providing and laying Autoclaved Aerated Concrete (AAC) block masonry work of approved manufacturer "
                "conforming to IS:2185 (Part-3) laid with ready-mix polymer-modified thin-bed block jointing adhesive complete."
            )
        if any(k in code for k in ("BRK", "BRICK")) or "BRICK" in name:
            return (
                "Providing and constructing first-class red clay brick masonry work in cement mortar 1:6 (1 cement : 6 sand) "
                "including curing, raking out joints, scaffolding, and staging complete at all levels."
            )

        # 3. Reinforcement Steel
        if any(k in code for k in ("STL", "REBAR", "TMT")) or (
            ("STEEL" in name or "REBAR" in name or "TMT" in name)
            and not any(k in name for k in ("PROP", "SHUTTER", "FORMWORK", "DOOR", "WINDOW", "SCREW", "HARDWARE", "FASTENER"))
        ):
            if material.status in {"NOT_AVAILABLE", "STRUCTURAL_REBAR_DATA_REQUIRED"} or material.total_quantity == 0.0:
                return (
                    "High Yield Strength Deformed (HYSD) TMT Fe 500D steel bars for RCC work including cutting, "
                    "bending, cranking, binding wire, and placing in position (NOTE: Rebar schedule not present in drawing)."
                )
            return (
                "Providing, cutting, bending, fabricating, hooking, cranking, placing in position and tying with "
                "18-gauge annealed binding wire Thermo-Mechanically Treated (TMT Fe 500D) steel reinforcement bars "
                "conforming to IS:1786 at all floor levels complete."
            )

        # 4. Ready-Mix / Structural Concrete (excluding AAC)
        if (any(k in code for k in ("CON", "RMC")) or "CONCRETE" in name) and "AAC" not in name:
            grade = (element.material_hint if element else "") or "M25"
            return (
                f"Providing and laying in position machine batched and machine mixed ready-mix concrete (RMC) "
                f"of design mix grade {grade} for structural reinforced concrete work including pumping, placing, "
                f"vibrating, compacting, curing, and finishing complete at all levels."
            )

        # 5. Plastering
        if "PLS" in code or "PLASTER" in name:
            return (
                "Providing and applying 12mm / 15mm thick smooth cement plaster in 1:6 cement mortar (1 cement : 6 fine sand) "
                "applied with plumb and line on internal masonry surfaces including scaffolding and curing complete for 14 days."
            )

        # 6. Partitions (Gypsum / Glass)
        if "GYP" in code or "GYPSUM" in name:
            return (
                "Providing and fixing 75 mm thick full-height double-skin gypsum board partition including GI framework "
                "(floor and ceiling tracks, vertical studs @ 610mm c/c), 12.5mm gypsum plasterboard on both faces, "
                "acoustic glass wool insulation, jointing compound, fiber mesh tape, screws, accessories and finishing complete."
            )
        if "GLS" in code or "GLASS" in name:
            return (
                "Providing and installing 10mm / 12mm thick architectural clear toughened safety glass partition with "
                "heavy-duty anodized aluminium perimeter u-channels, EPDM gaskets, structural silicone sealant, and floor spring patch fittings."
            )

        # 7. Flooring & Tiling
        if "TIL" in code or "FLOOR" in name or "VITRIFIED" in name:
            return (
                "Providing and laying 600x600 mm double charged vitrified floor tiles of approved make and shade laid over "
                "a base of polymer-modified tile adhesive bed, pointing joints with epoxy grout, including cleaning and curing complete."
            )
        if "SKT" in code or "SKIRTING" in name:
            return (
                "Providing and fixing 100mm high skirting matching the flooring flush/projected to wall plaster including "
                "backing adhesive, edge polishing, and neat joint pointing complete."
            )

        # 8. Painting
        if "PNT" in code or "PAINT" in name or "EMULSION" in name:
            return (
                "Applying two coats of approved premium acrylic interior emulsion paint over one coat of water-thinnable "
                "primer and two coats of acrylic wall putty to achieve a flawless, smooth, and even finish."
            )

        # 9. Waterproofing
        if "WTP" in code or "WATERPROOF" in name:
            return (
                "Providing and applying acrylic polymer-modified cementitious (APMC) waterproofing system in two coats over "
                "prepared concrete surface with minimum 300mm vertical upturn at walls including polymer cove fillets and water ponding test."
            )

        # Default fallback
        return f"Providing, supplying, and installing {material.material_name} complete in all respects as per standard architectural specifications."
