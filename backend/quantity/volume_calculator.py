from __future__ import annotations


def calculate_wall_volume(length_m: float, height_m: float, thickness_m: float) -> float:
    return length_m * height_m * thickness_m


def calculate_column_volume(width_m: float, depth_m: float, height_m: float, quantity: int = 1) -> float:
    return width_m * depth_m * height_m * quantity


def calculate_beam_volume(length_m: float, width_m: float, depth_m: float, quantity: int = 1) -> float:
    return length_m * width_m * depth_m * quantity


def calculate_slab_volume(area_m2: float, thickness_m: float) -> float:
    return area_m2 * thickness_m


def calculate_footing_volume(length_m: float, width_m: float, depth_m: float, quantity: int = 1) -> float:
    return length_m * width_m * depth_m * quantity
