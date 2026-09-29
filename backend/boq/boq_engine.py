from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from backend.models.cad_entity import CADEntity
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity
from backend.models.boq_item import BOQItem

from backend.geometry.geometry_engine import GeometryEngine
from backend.materials import MaterialEngine
from backend.quantity.deduction_engine import DeductionEngine
from backend.quantity.wastage_engine import WastageEngine
from .boq_item_builder import BOQItemBuilder
from .boq_validator import BOQValidator
from .boq_grouping import group_boq_items
from .boq_formatter import format_final_boq_response

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class BOQEngine:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATA_DIR
        self.geometry_engine = GeometryEngine()
        self.material_engine = MaterialEngine(self.data_dir / "material_rules.json")
        self.item_builder = BOQItemBuilder(self.data_dir / "boq_templates.json")
        self.validator = BOQValidator()
        self.deduction_engine = DeductionEngine()
        self.wastage_engine = WastageEngine(self.data_dir / "wastage_rules.json")

        self.rates_db: dict[str, Any] = {}
        rates_file = self.data_dir / "material_rates.json"
        if rates_file.exists():
            try:
                self.rates_db = json.loads(rates_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to load material rates: {e}")

    def generate_boq(
        self,
        drawing_data: dict[str, Any],
        rate_overrides: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Executes the full deterministic CAD-to-BOQ pipeline.
        """
        filename = drawing_data.get("filename", "drawing.dxf")
        units = drawing_data.get("units", "m")
        raw_entities = drawing_data.get("entities", [])
        layer_count = len(drawing_data.get("layers", []))
        entity_count = len(raw_entities)
        views = drawing_data.get("drawing_views", [])

        # 1. Geometry Detection
        elements: list[ConstructionElement] = self.geometry_engine.detect_all(drawing_data)

        # 2. Extract Openings for Deduction from Walls
        openings = []
        for el in elements:
            if el.element_type in {"DOOR", "WINDOW", "OPENING"}:
                w = float(el.geometry.get("width", 0.9) or 0.9)
                h = float(el.geometry.get("height", 2.1) or 2.1)
                openings.append({
                    "opening_id": el.element_id,
                    "type": el.element_type,
                    "width": w,
                    "height": h,
                    "area": w * h,
                    "source_entities": el.source_entities,
                })

        # 3. Apply Wall Deductions
        for el in elements:
            if el.element_type in {"WALL", "PARTITION"}:
                geo = el.geometry
                thickness = float(geo.get("thickness", 0.15) or 0.15)
                gross_vol = float(geo.get("volume", 0.0))
                gross_surf = float(geo.get("area", 0.0))

                if openings and gross_vol > 0:
                    # Apply opening deductions
                    ded_res = self.deduction_engine.apply_deductions_to_wall(
                        gross_volume_m3=gross_vol,
                        gross_surface_area_m2=gross_surf,
                        openings=openings[:len(openings)],  # associated openings
                        wall_thickness_m=thickness,
                    )
                    geo["deduction_volume"] = ded_res["deduction_volume_m3"]
                    geo["deduction_area"] = ded_res["deduction_surface_area_m2"]
                    geo["net_volume"] = ded_res["net_volume_m3"]
                    geo["net_area"] = ded_res["net_surface_area_m2"]
                    geo["volume"] = ded_res["net_volume_m3"]

        # 4. Material Systems Mapping
        combined_rates = dict(self.rates_db)
        if rate_overrides:
            combined_rates.update(rate_overrides)

        all_materials: list[MaterialQuantity] = []
        elem_by_id = {el.element_id: el for el in elements}

        for el in elements:
            mat_items = self.material_engine.calculate_materials_for_element(el, combined_rates)
            all_materials.extend(mat_items)

        # 5. Build BOQ Items
        boq_items: list[BOQItem] = []
        for idx, mat in enumerate(all_materials, start=1):
            source_elem = elem_by_id.get(mat.source_element_id)
            item = self.item_builder.build_item_from_material(
                item_no=idx,
                material=mat,
                element=source_elem,
                rates_db=combined_rates,
            )
            boq_items.append(item)

        # 6. Group BOQ Items Chronologically
        grouped = group_boq_items(boq_items)
        reordered_items: list[BOQItem] = []
        item_counter = 1
        for sec_name, items_in_sec in grouped.items():
            for it in items_in_sec:
                it.item_no = item_counter
                item_counter += 1
                reordered_items.append(it)

        # 7. Validation Audit
        validation_result = self.validator.validate_all(
            boq_items=reordered_items,
            elements=elements,
            openings=openings,
            views=views,
        )

        # 8. Format Final Response
        return format_final_boq_response(
            filename=filename,
            units=units,
            entity_count=entity_count,
            layer_count=layer_count,
            boq_items=reordered_items,
            validation_result=validation_result,
        )
