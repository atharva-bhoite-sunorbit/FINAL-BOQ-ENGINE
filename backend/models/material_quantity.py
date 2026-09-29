from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MaterialQuantity:
    material_code: str = ""
    material_name: str = ""
    category: str = "General"
    unit: str = "m2"
    net_quantity: float = 0.0
    wastage_percent: float = 0.0
    wastage_quantity: float = 0.0
    total_quantity: float = 0.0
    source_element_id: str = ""
    source_element_type: str = ""
    source_entities: list[str] = field(default_factory=list)
    source_layers: list[str] = field(default_factory=list)
    calculation_basis: str = ""
    status: str = "DERIVED"  # MEASURED | DERIVED | INFERRED | ASSUMED | NOT_AVAILABLE
    confidence: float = 0.90
    rate: float = 0.0
    amount: float = 0.0
    remarks: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        material_id: Optional[str] = None,
        material_code: Optional[str] = None,
        material_name: str = "",
        category: str = "General",
        unit: str = "m2",
        quantity: Optional[float] = None,
        net_quantity: Optional[float] = None,
        base_quantity: Optional[float] = None,
        base_unit: Optional[str] = None,
        consumption_factor: float = 1.0,
        wastage_percent: float = 0.0,
        wastage_quantity: Optional[float] = None,
        total_quantity: Optional[float] = None,
        source_element_id: str = "",
        source_element_type: str = "",
        source_entities: Optional[list[str]] = None,
        source_layers: Optional[list[str]] = None,
        calculation_basis: Optional[str] = None,
        derived_from: Optional[str] = None,
        status: str = "DERIVED",
        confidence: float = 0.90,
        rate: Optional[float] = None,
        unit_rate: Optional[float] = None,
        amount: Optional[float] = None,
        total_cost: Optional[float] = None,
        remarks: str = "",
        **kwargs: Any,
    ):
        self.material_code = material_code or material_id or "MAT-GEN"
        self.material_name = material_name
        self.category = category
        self.unit = unit

        net_q = net_quantity if net_quantity is not None else (quantity if quantity is not None else (base_quantity or 0.0))
        self.net_quantity = round(float(net_q), 4)
        self.wastage_percent = float(wastage_percent)

        if wastage_quantity is not None:
            self.wastage_quantity = round(float(wastage_quantity), 4)
        else:
            self.wastage_quantity = round(self.net_quantity * (self.wastage_percent / 100.0), 4)

        if total_quantity is not None:
            self.total_quantity = round(float(total_quantity), 4)
        else:
            self.total_quantity = round(self.net_quantity + self.wastage_quantity, 4)

        self.source_element_id = source_element_id
        self.source_element_type = source_element_type
        self.source_entities = source_entities or []
        self.source_layers = source_layers or []
        self.calculation_basis = calculation_basis or derived_from or ""
        self.status = status
        self.confidence = float(confidence)

        r = rate if rate is not None else (unit_rate or 0.0)
        self.rate = round(float(r), 2)

        a = amount if amount is not None else (total_cost if total_cost is not None else (self.total_quantity * self.rate))
        self.amount = round(float(a), 2)

        self.remarks = remarks
        self.extra = kwargs

    # Compatibility properties
    @property
    def material_id(self) -> str:
        return self.material_code

    @property
    def quantity(self) -> float:
        return self.net_quantity

    @property
    def unit_rate(self) -> float:
        return self.rate

    @property
    def total_cost(self) -> float:
        return self.amount

    @property
    def derived_from(self) -> str:
        return self.calculation_basis

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_code": self.material_code,
            "material_id": self.material_code,
            "material_name": self.material_name,
            "category": self.category,
            "unit": self.unit,
            "net_quantity": round(self.net_quantity, 4),
            "quantity": round(self.net_quantity, 4),
            "wastage_percent": self.wastage_percent,
            "wastage_quantity": round(self.wastage_quantity, 4),
            "total_quantity": round(self.total_quantity, 4),
            "source_element_id": self.source_element_id,
            "source_element_type": self.source_element_type,
            "source_entities": self.source_entities,
            "source_layers": self.source_layers,
            "calculation_basis": self.calculation_basis,
            "status": self.status,
            "confidence": round(self.confidence, 2),
            "rate": round(self.rate, 2),
            "unit_rate": round(self.rate, 2),
            "amount": round(self.amount, 2),
            "total_cost": round(self.amount, 2),
            "remarks": self.remarks,
            **self.extra,
        }
