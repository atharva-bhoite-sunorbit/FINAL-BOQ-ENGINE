from __future__ import annotations

import math
from typing import Sequence


def calculate_polygon_area(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1] - points[j][0] * points[i][1]
    return abs(area) / 2.0


def calculate_polyline_perimeter(points: Sequence[Sequence[float]], closed: bool = False) -> float:
    if len(points) < 2:
        return 0.0
    length = sum(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) for p1, p2 in zip(points, points[1:]))
    if closed and len(points) > 2:
        length += math.hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1])
    return length


def calculate_wall_surface_area(length_m: float, height_m: float, sides: int = 2) -> float:
    return length_m * height_m * sides
