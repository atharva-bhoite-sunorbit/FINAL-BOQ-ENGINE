from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BOQItem:
    item_no: int
    section: str
    element_type: str
    material: str
    description: str
    unit: str
    gross_quantity: float
    deduction_quantity: float
    net_quantity: float
    wastage_percent: float
    wastage_quantity: float
    total_quantity: float
    rate: float = 0.0
    material_rate: float = 0.0
    labour_rate: float = 0.0
    amount: float = 0.0
    calculation_basis: str = ""
    source_entities: list[str] = field(default_factory=list)
    source_layers: list[str] = field(default_factory=list)
    source_element_ids: list[str] = field(default_factory=list)
    status: str = "DERIVED"
    confidence: float = 0.95
    remarks: str = ""
    specification: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_no": self.item_no,
            "section": self.section,
            "element_type": self.element_type,
            "material": self.material,
            "description": self.description,
            "specification": self.specification,
            "unit": self.unit,
            "gross_quantity": round(self.gross_quantity, 4),
            "deduction_quantity": round(self.deduction_quantity, 4),
            "net_quantity": round(self.net_quantity, 4),
            "wastage_percent": self.wastage_percent,
            "wastage_quantity": round(self.wastage_quantity, 4),
            "total_quantity": round(self.total_quantity, 4),
            "quantity": round(self.total_quantity, 4),  # alias for standard views
            "material_rate": round(self.material_rate, 2),
            "labour_rate": round(self.labour_rate, 2),
            "rate": round(self.rate, 2),
            "amount": round(self.amount, 2),
            "calculation_basis": self.calculation_basis,
            "source_entities": self.source_entities,
            "source_layers": self.source_layers,
            "source_element_ids": self.source_element_ids,
            "source_elements": self.source_element_ids,
            "status": self.status,
            "confidence": round(self.confidence, 2),
            "remarks": self.remarks,
        }
