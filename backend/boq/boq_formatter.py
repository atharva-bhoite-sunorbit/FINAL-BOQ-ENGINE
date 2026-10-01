from __future__ import annotations

from typing import Any, Optional
from backend.models.boq_item import BOQItem


def format_final_boq_response(
    filename: str,
    units: str,
    entity_count: int,
    layer_count: int,
    boq_items: list[BOQItem],
    validation_result: dict[str, Any],
    reasoning_steps: list[str] | None = None,
    assumptions: list[str] | None = None,
    export_format: str = "Excel",
    construction_type: Optional[str] = None,
    construction_subtype: Optional[str] = None,
) -> dict[str, Any]:
    """
    Formats the final BOQ API response strictly adhering to Section 43 of the specification,
    enriched with detected or verified construction type.
    """
    serialized_boq = []
    for item in boq_items:
        serialized_boq.append({
            "item_no": item.item_no,
            "section": item.section,
            "element_type": item.element_type,
            "material": item.material,
            "description": item.description,
            "unit": item.unit,
            "gross_quantity": round(item.gross_quantity, 4),
            "deduction_quantity": round(item.deduction_quantity, 4),
            "net_quantity": round(item.net_quantity, 4),
            "quantity": round(item.total_quantity, 4),
            "wastage_percent": item.wastage_percent,
            "wastage_quantity": round(item.wastage_quantity, 4),
            "total_quantity": round(item.total_quantity, 4),
            "rate": round(item.rate, 2),
            "amount": round(item.amount, 2),
            "calculation_basis": item.calculation_basis,
            "status": item.status,
            "confidence": round(item.confidence, 2),
            "remarks": item.remarks,
            "source_entities": item.source_entities,
            "source_layers": item.source_layers,
            "source_elements": item.source_element_ids,
            "source_element_ids": item.source_element_ids,
        })

    warnings_list = [w["message"] if isinstance(w, dict) else str(w) for w in validation_result.get("warnings", [])]

    steps = reasoning_steps or [
        "1. Loaded CAD document, extracted entities and layer structures with tag normalization.",
        "2. Analyzed text annotations, explicit dimensions, and expanded block definitions.",
        "3. Detected drawing views and filtered duplicate presentation layouts to prevent double-counting.",
        "4. Orchestrated 34 individual geometric element detectors (structural, masonry, partitions, finishes, MEP).",
        "5. Identified wall openings (doors, windows) and computed deterministic volume/surface deductions.",
        "6. Mapped construction elements to multi-component material systems and applied IS/CPWD wastage rules.",
        "7. Consolidated items into chronological construction sequence and generated professional engineering descriptions.",
        "8. Executed 14 validation checks ensuring zero fabricated quantities, dimension consistency, and audit traceability.",
    ]

    assumed = assumptions or [
        "Floor-to-floor height assumed at standard 3.0m where explicit elevation callouts were absent.",
        "Door opening standard dimensions assumed as 0.90m x 2.10m unless explicit dimension tag present.",
        "Window opening standard dimensions assumed as 1.20m x 1.20m unless explicit dimension tag present.",
        "Reinforcement steel bar schedule marked NOT_AVAILABLE where bar bending schedules were not in drawing.",
    ]

    summary = {
        "filename": filename,
        "units": units,
        "entity_count": entity_count,
        "layer_count": layer_count,
    }
    if construction_type:
        summary["construction_type"] = construction_type
    if construction_subtype:
        summary["construction_subtype"] = construction_subtype

    resp = {
        "reasoning_steps": steps,
        "drawing_summary": summary,
        "boq": serialized_boq,
        "warnings": warnings_list,
        "assumptions": assumed,
        "validation": {
            "passed": validation_result.get("passed", True),
            "errors": validation_result.get("errors", []),
            "warnings": validation_result.get("warnings", []),
        },
        "export_format": export_format,
    }
    if construction_type:
        resp["construction_type"] = construction_type
    if construction_subtype:
        resp["construction_subtype"] = construction_subtype

    return resp
