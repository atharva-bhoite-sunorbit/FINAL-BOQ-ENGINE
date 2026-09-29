from __future__ import annotations

import math
from typing import Sequence


def calculate_segments_total_length(segments: Sequence[dict]) -> float:
    return sum(float(s.get("length_m", s.get("length", 0.0))) for s in segments)


def calculate_perimeter_from_dimensions(length_m: float, width_m: float) -> float:
    return 2.0 * (length_m + width_m)
