from __future__ import annotations

from typing import Any
from backend.models.boq_item import BOQItem
from backend.models.construction_element import ConstructionElement
from backend.models.cad_entity import CADEntity


class BOQValidator:
    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance

    def validate_all(
        self,
        boq_items: list[BOQItem],
        elements: list[ConstructionElement] | None = None,
        entities: list[CADEntity] | None = None,
        openings: list[dict[str, Any]] | None = None,
        views: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        elements = elements or []
        entities = entities or []
        openings = openings or []
        views = views or []

        # 1. Validate Duplicate Entities
        seen_handles: set[str] = set()
        duplicate_entities = 0
        for e in entities:
            h = e.handle or e.entity_id
            if h in seen_handles:
                duplicate_entities += 1
            else:
                seen_handles.add(h)
        if duplicate_entities > 0:
            warnings.append({
                "code": "DUPLICATE_ENTITIES",
                "message": f"Found {duplicate_entities} duplicate CAD entity handles.",
            })

        # 2. Validate Duplicate Elements
        elem_ids: set[str] = set()
        for el in elements:
            if el.element_id in elem_ids:
                errors.append({
                    "code": "DUPLICATE_ELEMENT",
                    "element_id": el.element_id,
                    "message": f"Duplicate construction element ID: {el.element_id}",
                })
            elem_ids.add(el.element_id)

        # 3. Validate Duplicate Openings
        op_ids: set[str] = set()
        for op in openings:
            oid = op.get("opening_id") or op.get("element_id", "")
            if oid and oid in op_ids:
                warnings.append({
                    "code": "DUPLICATE_OPENING",
                    "opening_id": oid,
                    "message": f"Duplicate opening definition: {oid}",
                })
            if oid:
                op_ids.add(oid)

        # 4. Validate Duplicate Drawing Views
        view_titles: set[str] = set()
        for v in views:
            title = v.get("title", "")
            if title and title in view_titles:
                warnings.append({
                    "code": "DUPLICATE_DRAWING_VIEW",
                    "view": title,
                    "message": f"Repeated drawing view/sheet detected: {title}. Verified presentation copies to avoid double-counting.",
                })
            if title:
                view_titles.add(title)

        # 5. Validate Impossible Dimensions / Missing Height / Thickness in Elements
        for el in elements:
            geo = el.geometry
            etype = el.element_type.upper()
            length = float(geo.get("length", 0.0))
            height = float(geo.get("height", 0.0))
            thickness = float(geo.get("thickness", 0.0))
            area = float(geo.get("area", 0.0))

            if etype in {"WALL", "PARTITION"}:
                if height <= 0:
                    warnings.append({
                        "code": "MISSING_HEIGHT",
                        "element_id": el.element_id,
                        "message": f"Wall/Partition {el.element_id} has missing or zero height; standard assumption used.",
                    })
                if thickness <= 0:
                    warnings.append({
                        "code": "MISSING_THICKNESS",
                        "element_id": el.element_id,
                        "message": f"Wall/Partition {el.element_id} has missing thickness; default used.",
                    })
                if length > 250.0:
                    warnings.append({
                        "code": "IMPOSSIBLE_DIMENSION",
                        "element_id": el.element_id,
                        "message": f"Wall length {length:.2f}m exceeds typical building span limit (250m).",
                    })

        # 6. Validate BOQ Items Calculations, Negative/Zero Quantities & Opening Deductions
        for item in boq_items:
            # Check deduction > gross
            if item.gross_quantity > 0 and item.deduction_quantity > item.gross_quantity:
                errors.append({
                    "code": "INVALID_QUANTITY",
                    "item_no": item.item_no,
                    "material": item.material,
                    "message": f"Deduction quantity ({item.deduction_quantity}) exceeds gross quantity ({item.gross_quantity}).",
                })

            # Check negative quantities
            if item.net_quantity < 0 or item.total_quantity < 0:
                errors.append({
                    "code": "NEGATIVE_QUANTITY",
                    "item_no": item.item_no,
                    "material": item.material,
                    "message": f"Calculated quantity is negative ({item.total_quantity}).",
                })

            # Check zero quantities (allowed only if NOT_AVAILABLE)
            if item.total_quantity == 0 and item.status != "NOT_AVAILABLE":
                warnings.append({
                    "code": "ZERO_QUANTITY",
                    "item_no": item.item_no,
                    "material": item.material,
                    "message": f"BOQ item has zero quantity with status {item.status}.",
                })

            # Check wastage calculation
            expected_wastage = round(item.net_quantity * (item.wastage_percent / 100.0), 4)
            if abs(item.wastage_quantity - expected_wastage) > 0.05:
                warnings.append({
                    "code": "WASTAGE_CALCULATION_MISMATCH",
                    "item_no": item.item_no,
                    "message": f"Wastage arithmetic mismatch: expected {expected_wastage}, got {item.wastage_quantity}",
                })

            # Check total quantity = net + wastage
            expected_total = round(item.net_quantity + item.wastage_quantity, 4)
            if abs(item.total_quantity - expected_total) > 0.05:
                errors.append({
                    "code": "TOTAL_CALCULATION_MISMATCH",
                    "item_no": item.item_no,
                    "message": f"Total quantity mismatch: expected {expected_total}, got {item.total_quantity}",
                })

            # Check amount = total_quantity * rate
            expected_amount = round(item.total_quantity * item.rate, 2)
            if abs(item.amount - expected_amount) > 1.0:
                warnings.append({
                    "code": "AMOUNT_CALCULATION_MISMATCH",
                    "item_no": item.item_no,
                    "message": f"Line amount mismatch: expected {expected_amount}, got {item.amount}",
                })

        passed = len(errors) == 0
        return {
            "passed": passed,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
        }
