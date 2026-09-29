from __future__ import annotations

from typing import Any

# Internal SI conversion factors to base SI units:
# Length -> meters (m)
# Area -> square meters (m2)
# Volume -> cubic meters (m3)
# Weight -> kilograms (kg)

LENGTH_TO_METERS = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "inch": 0.0254,
    "in": 0.0254,
    "feet": 0.3048,
    "ft": 0.3048,
    "rft": 0.3048,
    "rmt": 1.0,
}

AREA_TO_SQM = {
    "mm2": 1e-6,
    "cm2": 1e-4,
    "m2": 1.0,
    "sqm": 1.0,
    "sqft": 0.092903,
    "sqin": 0.00064516,
    "sqyd": 0.836127,
}

VOLUME_TO_CUM = {
    "m3": 1.0,
    "cum": 1.0,
    "cuft": 0.0283168,
    "cft": 0.0283168,
    "litre": 0.001,
    "litres": 0.001,
}

WEIGHT_TO_KG = {
    "kg": 1.0,
    "g": 0.001,
    "ton": 1000.0,
    "mt": 1000.0,
    "quintal": 100.0,
}


def to_meters(value: float, unit: str) -> float:
    return value * LENGTH_TO_METERS.get(unit.lower(), 1.0)


def from_meters(value_m: float, target_unit: str) -> float:
    factor = LENGTH_TO_METERS.get(target_unit.lower(), 1.0)
    return value_m / factor if factor != 0 else value_m


def to_sqm(value: float, unit: str) -> float:
    return value * AREA_TO_SQM.get(unit.lower(), 1.0)


def from_sqm(value_sqm: float, target_unit: str) -> float:
    factor = AREA_TO_SQM.get(target_unit.lower(), 1.0)
    return value_sqm / factor if factor != 0 else value_sqm


def to_cum(value: float, unit: str) -> float:
    return value * VOLUME_TO_CUM.get(unit.lower(), 1.0)


def from_cum(value_cum: float, target_unit: str) -> float:
    factor = VOLUME_TO_CUM.get(target_unit.lower(), 1.0)
    return value_cum / factor if factor != 0 else value_cum


def to_kg(value: float, unit: str) -> float:
    return value * WEIGHT_TO_KG.get(unit.lower(), 1.0)


def from_kg(value_kg: float, target_unit: str) -> float:
    factor = WEIGHT_TO_KG.get(target_unit.lower(), 1.0)
    return value_kg / factor if factor != 0 else value_kg
