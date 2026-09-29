from __future__ import annotations

import math
from typing import Any, Optional, Sequence


def normalize_length(value: float, units: str) -> float:
    """Normalizes length from given drawing units to meters."""
    u = (units or "m").lower().strip()
    factor = {
        "mm": 0.001,
        "millimeter": 0.001,
        "millimeters": 0.001,
        "cm": 0.01,
        "centimeter": 0.01,
        "centimeters": 0.01,
        "m": 1.0,
        "meter": 1.0,
        "meters": 1.0,
        "inch": 0.0254,
        "inches": 0.0254,
        "in": 0.0254,
        "feet": 0.3048,
        "foot": 0.3048,
        "ft": 0.3048,
        "drawing units": 1.0,
    }.get(u, 1.0)
    return float(value) * factor


def normalize_area(value: float, units: str) -> float:
    """Normalizes area from given drawing units to square meters."""
    u = (units or "m").lower().strip()
    factor = {
        "mm": 0.001,
        "millimeter": 0.001,
        "cm": 0.01,
        "centimeter": 0.01,
        "m": 1.0,
        "meter": 1.0,
        "inch": 0.0254,
        "in": 0.0254,
        "feet": 0.3048,
        "ft": 0.3048,
        "drawing units": 1.0,
    }.get(u, 1.0)
    return float(value) * (factor ** 2)


def normalize_volume(value: float, units: str) -> float:
    """Normalizes volume from given drawing units to cubic meters."""
    u = (units or "m").lower().strip()
    factor = {
        "mm": 0.001,
        "millimeter": 0.001,
        "cm": 0.01,
        "centimeter": 0.01,
        "m": 1.0,
        "meter": 1.0,
        "inch": 0.0254,
        "in": 0.0254,
        "feet": 0.3048,
        "ft": 0.3048,
        "drawing units": 1.0,
    }.get(u, 1.0)
    return float(value) * (factor ** 3)


def _point(point: Sequence[float]) -> list[float]:
    """Helper to convert point to 2D or 3D coordinate list."""
    if len(point) >= 3:
        return [float(point[0]), float(point[1]), float(point[2])]
    return [float(point[0]), float(point[1])]


def start_end_points(points: Sequence[Sequence[float]]) -> tuple[Optional[list[float]], Optional[list[float]]]:
    """Extracts start and end points from coordinate list."""
    if not points:
        return None, None
    return _point(points[0]), _point(points[-1])


def distance_point_to_point(p1: Sequence[float], p2: Sequence[float]) -> float:
    """Euclidean distance between two 2D or 3D points."""
    dx = float(p2[0]) - float(p1[0])
    dy = float(p2[1]) - float(p1[1])
    dz = float(p2[2]) - float(p1[2]) if len(p1) > 2 and len(p2) > 2 else 0.0
    return math.sqrt(dx * dx + dy * dy + dz * dz)


_distance = distance_point_to_point


def calculate_length(points: Sequence[Sequence[float]], closed: bool = False) -> float:
    """Calculates total length of open or closed polyline."""
    if len(points) < 2:
        return 0.0
    tot = sum(distance_point_to_point(a, b) for a, b in zip(points, points[1:]))
    if closed and len(points) > 2:
        tot += distance_point_to_point(points[-1], points[0])
    return tot


_polyline_length = calculate_length


def calculate_perimeter(points: Sequence[Sequence[float]], closed: bool = True) -> float:
    """Calculates perimeter of closed or open shape."""
    return calculate_length(points, closed=closed)


def calculate_area(points: Sequence[Sequence[float]]) -> float:
    """Calculates 2D planar polygon area using the shoelace algorithm."""
    if len(points) < 3:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        area += float(points[i][0]) * float(points[j][1])
        area -= float(points[j][0]) * float(points[i][1])
    return abs(area) / 2.0


_shoelace = calculate_area


def calculate_bounding_box(points: Sequence[Sequence[float]]) -> dict[str, float]:
    """Calculates 2D or 3D bounding box for point list."""
    if not points:
        return {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0, "width": 0.0, "height": 0.0}
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    bbox = {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }
    if any(len(p) > 2 for p in points):
        zs = [float(p[2]) for p in points if len(p) > 2]
        if zs:
            bbox["min_z"] = min(zs)
            bbox["max_z"] = max(zs)
            bbox["depth"] = max(zs) - min(zs)
    return bbox


def calculate_centroid(points: Sequence[Sequence[float]]) -> list[float]:
    """Calculates geometric centroid of a polygon or point cloud."""
    if not points:
        return [0.0, 0.0]
    if len(points) < 3:
        cx = sum(float(p[0]) for p in points) / len(points)
        cy = sum(float(p[1]) for p in points) / len(points)
        return [cx, cy]

    # Polygon centroid
    signed_area = 0.0
    cx = 0.0
    cy = 0.0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        x0, y0 = float(points[i][0]), float(points[i][1])
        x1, y1 = float(points[j][0]), float(points[j][1])
        cross = x0 * y1 - x1 * y0
        signed_area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross

    signed_area *= 0.5
    if abs(signed_area) < 1e-9:
        # Collinear or degenerate, fallback to arithmetic mean
        return [sum(float(p[0]) for p in points) / n, sum(float(p[1]) for p in points) / n]

    cx /= (6.0 * signed_area)
    cy /= (6.0 * signed_area)
    return [cx, cy]


def calculate_orientation(p1: Sequence[float], p2: Sequence[float]) -> dict[str, float]:
    """Calculates orientation angle of a segment in radians and degrees (0 to 180)."""
    dx = float(p2[0]) - float(p1[0])
    dy = float(p2[1]) - float(p1[1])
    angle = math.atan2(dy, dx) % math.pi
    return {
        "angle_rad": angle,
        "angle_deg": math.degrees(angle),
    }


def are_parallel(
    p1: Sequence[float],
    p2: Sequence[float],
    q1: Sequence[float],
    q2: Sequence[float],
    angle_tol_rad: float = 0.08,
) -> bool:
    """Tests if two line segments (p1-p2) and (q1-q2) are parallel within angle tolerance."""
    dx1 = float(p2[0]) - float(p1[0])
    dy1 = float(p2[1]) - float(p1[1])
    len1 = math.hypot(dx1, dy1)
    if len1 < 1e-7:
        return False

    dx2 = float(q2[0]) - float(q1[0])
    dy2 = float(q2[1]) - float(q1[1])
    len2 = math.hypot(dx2, dy2)
    if len2 < 1e-7:
        return False

    ang1 = math.atan2(dy1, dx1) % math.pi
    ang2 = math.atan2(dy2, dx2) % math.pi
    diff = abs(ang1 - ang2)
    return diff <= angle_tol_rad or abs(diff - math.pi) <= angle_tol_rad


def offset_distance(
    p1: Sequence[float],
    p2: Sequence[float],
    q1: Sequence[float],
    q2: Sequence[float],
) -> float:
    """Calculates perpendicular distance between two parallel line segments."""
    x1, y1 = float(p1[0]), float(p1[1])
    x2, y2 = float(p2[0]), float(p2[1])
    len_p = math.hypot(x2 - x1, y2 - y1)
    if len_p < 1e-7:
        return distance_point_to_point(p1, q1)
    dist1 = abs((y2 - y1) * float(q1[0]) - (x2 - x1) * float(q1[1]) + x2 * y1 - y2 * x1) / len_p
    dist2 = abs((y2 - y1) * float(q2[0]) - (x2 - x1) * float(q2[1]) + x2 * y1 - y2 * x1) / len_p
    return (dist1 + dist2) / 2.0


def distance_point_to_segment(
    p: Sequence[float],
    s1: Sequence[float],
    s2: Sequence[float],
) -> float:
    """Calculates shortest distance from a point p to line segment s1-s2."""
    px, py = float(p[0]), float(p[1])
    x1, y1 = float(s1[0]), float(s1[1])
    x2, y2 = float(s2[0]), float(s2[1])
    dx, dy = x2 - x1, y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-9:
        return math.hypot(px - x1, py - y1)

    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def are_collinear(
    p1: Sequence[float],
    p2: Sequence[float],
    q1: Sequence[float],
    q2: Sequence[float],
    dist_tol: float = 0.05,
    angle_tol_rad: float = 0.08,
) -> bool:
    """Tests if two line segments lie along the same line within tolerance."""
    if not are_parallel(p1, p2, q1, q2, angle_tol_rad):
        return False
    d1 = distance_point_to_segment(q1, p1, p2)
    d2 = distance_point_to_segment(q2, p1, p2)
    perp_d = offset_distance(p1, p2, q1, q2)
    return perp_d <= dist_tol or min(d1, d2) <= dist_tol


def segments_intersect(
    p1: Sequence[float],
    p2: Sequence[float],
    q1: Sequence[float],
    q2: Sequence[float],
) -> tuple[bool, Optional[list[float]]]:
    """
    Tests if two 2D line segments intersect.
    Returns (True, [ix, iy]) if intersection exists, otherwise (False, None).
    """
    x1, y1 = float(p1[0]), float(p1[1])
    x2, y2 = float(p2[0]), float(p2[1])
    x3, y3 = float(q1[0]), float(q1[1])
    x4, y4 = float(q2[0]), float(q2[1])

    denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
    if abs(denom) < 1e-9:
        return False, None

    ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
    ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom

    if 0.0 <= ua <= 1.0 and 0.0 <= ub <= 1.0:
        ix = x1 + ua * (x2 - x1)
        iy = y1 + ua * (y2 - y1)
        return True, [ix, iy]

    return False, None


def point_in_polygon(point: Sequence[float], polygon_pts: Sequence[Sequence[float]]) -> bool:
    """Tests if 2D point is inside a polygon using ray casting."""
    if len(polygon_pts) < 3:
        return False
    px, py = float(point[0]), float(point[1])
    inside = False
    n = len(polygon_pts)
    for i in range(n):
        j = (i + 1) % n
        xi, yi = float(polygon_pts[i][0]), float(polygon_pts[i][1])
        xj, yj = float(polygon_pts[j][0]), float(polygon_pts[j][1])
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
    return inside


def polygon_contains_polygon(
    outer_pts: Sequence[Sequence[float]],
    inner_pts: Sequence[Sequence[float]],
) -> bool:
    """Tests if outer polygon completely contains all points of inner polygon."""
    if len(outer_pts) < 3 or not inner_pts:
        return False
    b_out = calculate_bounding_box(outer_pts)
    b_in = calculate_bounding_box(inner_pts)
    if (
        b_in["min_x"] < b_out["min_x"] - 1e-6
        or b_in["max_x"] > b_out["max_x"] + 1e-6
        or b_in["min_y"] < b_out["min_y"] - 1e-6
        or b_in["max_y"] > b_out["max_y"] + 1e-6
    ):
        return False
    return all(point_in_polygon(p, outer_pts) for p in inner_pts)


def spatial_relation(
    pts_a: Sequence[Sequence[float]],
    pts_b: Sequence[Sequence[float]],
    touch_tol: float = 0.05,
) -> str:
    """
    Determines spatial relationship between two geometries:
    CONTAINS, CONTAINED_BY, OVERLAPS, TOUCHES, ADJACENT, DISJOINT
    """
    if not pts_a or not pts_b:
        return "DISJOINT"

    box_a = calculate_bounding_box(pts_a)
    box_b = calculate_bounding_box(pts_b)

    if (
        box_a["max_x"] < box_b["min_x"] - touch_tol
        or box_a["min_x"] > box_b["max_x"] + touch_tol
        or box_a["max_y"] < box_b["min_y"] - touch_tol
        or box_a["min_y"] > box_b["max_y"] + touch_tol
    ):
        return "DISJOINT"

    if len(pts_a) >= 3 and polygon_contains_polygon(pts_a, pts_b):
        return "CONTAINS"
    if len(pts_b) >= 3 and polygon_contains_polygon(pts_b, pts_a):
        return "CONTAINED_BY"

    for i in range(len(pts_a) - 1):
        for j in range(len(pts_b) - 1):
            hit, _ = segments_intersect(pts_a[i], pts_a[i + 1], pts_b[j], pts_b[j + 1])
            if hit:
                return "OVERLAPS"

    min_d = min(distance_point_to_point(pa, pb) for pa in pts_a for pb in pts_b)
    if min_d <= 1e-4:
        return "TOUCHES"
    if min_d <= touch_tol:
        return "ADJACENT"

    return "DISJOINT"


def calculate_volume(area: float, height_or_thickness: float) -> float:
    """Calculates volume from cross-sectional area and height/thickness."""
    return float(area) * float(height_or_thickness)


def normalize_geometry(entity_dict: dict[str, Any], units: str) -> dict[str, Any]:
    """
    Normalizes all coordinates, lengths, areas, and bounding boxes within an entity record
    to standard SI units (meters, square meters, cubic meters).
    """
    normalized = dict(entity_dict)
    u = (units or "m").lower()

    if "length" in normalized and normalized["length"] is not None:
        normalized["length"] = normalize_length(float(normalized["length"]), u)
    if "perimeter" in normalized and normalized["perimeter"] is not None:
        normalized["perimeter"] = normalize_length(float(normalized["perimeter"]), u)
    if "area" in normalized and normalized["area"] is not None:
        normalized["area"] = normalize_area(float(normalized["area"]), u)
    if "thickness" in normalized and normalized["thickness"] is not None:
        normalized["thickness"] = normalize_length(float(normalized["thickness"]), u)
    if "elevation" in normalized and normalized["elevation"] is not None:
        normalized["elevation"] = normalize_length(float(normalized["elevation"]), u)

    if "points" in normalized and normalized["points"]:
        normalized["points"] = [
            [normalize_length(p[0], u), normalize_length(p[1], u)]
            for p in normalized["points"]
        ]
    if "center" in normalized and normalized["center"]:
        normalized["center"] = [
            normalize_length(normalized["center"][0], u),
            normalize_length(normalized["center"][1], u),
        ]
    if "radius" in normalized and normalized["radius"] is not None:
        normalized["radius"] = normalize_length(float(normalized["radius"]), u)
    if "point" in normalized and normalized["point"]:
        normalized["point"] = [
            normalize_length(normalized["point"][0], u),
            normalize_length(normalized["point"][1], u),
        ]
    if "bbox" in normalized and normalized["bbox"]:
        b = normalized["bbox"]
        normalized["bbox"] = {
            "min_x": normalize_length(b["min_x"], u),
            "min_y": normalize_length(b["min_y"], u),
            "max_x": normalize_length(b["max_x"], u),
            "max_y": normalize_length(b["max_y"], u),
            "width": normalize_length(b["width"], u),
            "height": normalize_length(b["height"], u),
        }

    normalized["units"] = "m"
    return normalized


def entity_record(entity: Any, units: str) -> dict[str, Any]:
    """
    Builds a complete, normalized entity record dictionary from an ezdxf entity.
    Extracts handle, layer, color, linetype, lineweight, visibility, layout,
    elevation, thickness, coordinates, rotation, scale, attributes.
    """
    kind = entity.dxftype()
    layer = getattr(entity.dxf, "layer", "0")
    color = getattr(entity.dxf, "color", None)
    linetype = getattr(entity.dxf, "linetype", "ByLayer")
    lineweight = getattr(entity.dxf, "lineweight", None)
    elevation = float(getattr(entity.dxf, "elevation", 0.0) or 0.0)
    thickness = float(getattr(entity.dxf, "thickness", 0.0) or 0.0)
    rotation = float(getattr(entity.dxf, "rotation", 0.0) or 0.0)
    handle = getattr(entity.dxf, "handle", None)
    in_paperspace = bool(getattr(entity.dxf, "paperspace", 0))

    record: dict[str, Any] = {
        "handle": handle,
        "id": handle or "E000",
        "entity_type": kind,
        "type": kind,
        "layer": layer,
        "color": color,
        "linetype": linetype,
        "lineweight": lineweight,
        "elevation": elevation,
        "thickness": thickness,
        "rotation": rotation,
        "in_paperspace": in_paperspace,
        "units": units,
        "block_name": getattr(entity.dxf, "name", None) if kind == "INSERT" else None,
        "closed": False,
        "points": [],
    }

    if kind == "LINE":
        start, end = entity.dxf.start, entity.dxf.end
        p1, p2 = _point(start), _point(end)
        record["points"] = [p1, p2]
        record["length"] = distance_point_to_point(p1, p2)
        record["start_point"] = p1
        record["end_point"] = p2

    elif kind in {"LWPOLYLINE", "POLYLINE"}:
        if kind == "LWPOLYLINE":
            pts = [_point(p) for p in entity.get_points("xy") if len(p) >= 2]
        else:
            pts = [_point(v.dxf.location) for v in entity.vertices]
        is_closed = bool(getattr(entity, "closed", False) or getattr(entity.dxf, "flags", 0) & 1)
        record["points"] = pts
        record["closed"] = is_closed
        record["perimeter"] = calculate_length(pts, is_closed)
        record["area"] = calculate_area(pts) if (is_closed or len(pts) >= 3) else 0.0
        record["length"] = record["perimeter"]
        if pts:
            record["start_point"] = pts[0]
            record["end_point"] = pts[-1]
            record["centroid"] = calculate_centroid(pts)

    elif kind == "CIRCLE":
        center = _point(entity.dxf.center)
        radius = float(entity.dxf.radius)
        record.update({
            "center": center,
            "radius": radius,
            "closed": True,
            "perimeter": 2.0 * math.pi * radius,
            "area": math.pi * (radius ** 2),
            "length": 2.0 * math.pi * radius,
            "centroid": center[:2],
        })

    elif kind == "ARC":
        center = _point(entity.dxf.center)
        radius = float(entity.dxf.radius)
        sa = float(getattr(entity.dxf, "start_angle", 0.0))
        ea = float(getattr(entity.dxf, "end_angle", 360.0))
        sweep = (ea - sa) % 360.0
        sweep_rad = math.radians(sweep)
        record.update({
            "center": center,
            "radius": radius,
            "start_angle": sa,
            "end_angle": ea,
            "sweep_angle": sweep,
            "length": abs(radius * sweep_rad),
        })

    elif kind == "ELLIPSE":
        center = _point(entity.dxf.center)
        maj = entity.dxf.major_axis
        maj_len = math.hypot(float(maj.x), float(maj.y))
        ratio = float(entity.dxf.ratio)
        min_len = maj_len * ratio
        area = math.pi * maj_len * min_len
        perim = math.pi * (3.0 * (maj_len + min_len) - math.sqrt((3.0 * maj_len + min_len) * (maj_len + 3.0 * min_len)))
        record.update({
            "center": center,
            "major_axis_len": maj_len,
            "ratio": ratio,
            "closed": True,
            "area": area,
            "perimeter": perim,
            "length": perim,
            "centroid": center[:2],
        })

    elif kind == "SPLINE":
        pts: list[list[float]] = []
        if hasattr(entity, "control_points") and entity.control_points:
            pts = [_point(p) for p in entity.control_points if len(p) >= 2]
        elif hasattr(entity, "fit_points") and entity.fit_points:
            pts = [_point(p) for p in entity.fit_points if len(p) >= 2]
        is_closed = bool(getattr(entity, "closed", False))
        record["points"] = pts
        record["closed"] = is_closed
        record["length"] = calculate_length(pts, is_closed)
        if pts:
            record["start_point"] = pts[0]
            record["end_point"] = pts[-1]
            record["centroid"] = calculate_centroid(pts)

    elif kind in {"TEXT", "MTEXT"}:
        text_content = entity.plain_text() if kind == "MTEXT" else getattr(entity.dxf, "text", "")
        insert_pt = _point(entity.dxf.insert)
        height = float(getattr(entity.dxf, "height", 0.0) or 0.0)
        style = getattr(entity.dxf, "style", "Standard")
        record.update({
            "text": text_content,
            "point": insert_pt,
            "height": height,
            "style": style,
        })

    elif kind == "INSERT":
        insert_pt = _point(entity.dxf.insert)
        scale = [
            float(getattr(entity.dxf, "xscale", 1.0) or 1.0),
            float(getattr(entity.dxf, "yscale", 1.0) or 1.0),
            float(getattr(entity.dxf, "zscale", 1.0) or 1.0),
        ]
        attribs = {}
        if hasattr(entity, "attribs"):
            for attr in entity.attribs:
                attribs[attr.dxf.tag] = attr.dxf.text
        record.update({
            "point": insert_pt,
            "scale": scale,
            "attributes": attribs,
        })

    elif kind == "DIMENSION":
        dim_text = getattr(entity.dxf, "text", "") or ""
        meas = _dimension_measurement(entity)
        record.update({
            "text": dim_text,
            "measurement": meas,
            "dimension_type": getattr(entity.dxf, "dimtype", 0),
        })
        if hasattr(entity.dxf, "defpoint"):
            record["defpoint"] = _point(entity.dxf.defpoint)
        if hasattr(entity.dxf, "defpoint2"):
            record["defpoint2"] = _point(entity.dxf.defpoint2)
        if hasattr(entity.dxf, "defpoint3"):
            record["defpoint3"] = _point(entity.dxf.defpoint3)

    elif kind == "HATCH":
        record["pattern_name"] = getattr(entity.dxf, "pattern_name", "")
        record["pattern_scale"] = float(getattr(entity.dxf, "pattern_scale", 1.0) or 1.0)
        record["pattern_angle"] = float(getattr(entity.dxf, "pattern_angle", 0.0) or 0.0)
        record["area"] = _hatch_area(entity)

    elif kind in {"3DFACE", "SOLID", "TRACE"}:
        pts = []
        for vname in ("vtx0", "vtx1", "vtx2", "vtx3"):
            if hasattr(entity.dxf, vname):
                pts.append(_point(getattr(entity.dxf, vname)))
        record["points"] = pts
        record["closed"] = True
        record["area"] = calculate_area(pts) if len(pts) >= 3 else 0.0
        record["length"] = calculate_perimeter(pts, True)
        if pts:
            record["centroid"] = calculate_centroid(pts)

    elif kind == "POINT":
        loc = _point(entity.dxf.location)
        record["point"] = loc
        record["points"] = [loc]

    elif kind in {"LEADER", "MLEADER"}:
        pts = []
        if hasattr(entity, "vertices"):
            pts = [_point(v) for v in entity.vertices]
        record["points"] = pts
        record["length"] = calculate_length(pts, False)

    elif kind == "MESH":
        record["closed"] = True
        record["points"] = []
        if hasattr(entity, "vertices"):
            record["points"] = [_point(v) for v in entity.vertices]

    else:
        record["type"] = "UNKNOWN"
        record["raw_metadata"] = f"dxftype={kind}"

    _add_bounds(record)
    return record


def _dimension_measurement(entity: Any) -> Optional[float]:
    for attr in ("actual_measurement", "measurement"):
        val = getattr(entity.dxf, attr, None)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None


def _hatch_area(entity: Any) -> float:
    tot_area = 0.0
    try:
        if hasattr(entity, "paths") and entity.paths:
            for path in entity.paths:
                pts: list[list[float]] = []
                if hasattr(path, "vertices") and path.vertices:
                    pts = [_point(v) for v in path.vertices if len(v) >= 2]
                elif hasattr(path, "edges") and path.edges:
                    for edge in path.edges:
                        if hasattr(edge, "start"):
                            pts.append(_point(edge.start))
                        if hasattr(edge, "end"):
                            pts.append(_point(edge.end))
                if len(pts) >= 3:
                    tot_area += calculate_area(pts)
        if tot_area <= 0.0 and hasattr(entity, "dxf"):
            tot_area = float(getattr(entity.dxf, "area", 0.0) or 0.0)
    except Exception:
        tot_area = 0.0
    return tot_area


def _add_bounds(record: dict[str, Any]) -> None:
    points: list[list[float]] = list(record.get("points", []))
    if not points and record.get("center") and record.get("radius") is not None:
        cx, cy = record["center"][0], record["center"][1]
        r = record["radius"]
        points = [[cx - r, cy - r], [cx + r, cy + r]]
    if not points and record.get("point"):
        points = [record["point"][:2]]
    if not points:
        return
    bbox = calculate_bounding_box(points)
    record["bbox"] = bbox
    record["width"] = bbox["width"]
    record["height"] = bbox["height"]


def merge_parallel_walls(wall_segments: list[dict[str, Any]], units: str) -> list[dict[str, Any]]:
    """
    Detects pairs of parallel lines representing two faces of the same wall
    (standard thickness between 0.07m and 0.40m) and deduplicates them into single centerlines.
    """
    if len(wall_segments) < 2:
        return wall_segments

    unit_factor = normalize_length(1.0, units)
    min_dist = 0.07 / (unit_factor if unit_factor > 0 else 1.0)
    max_dist = 0.40 / (unit_factor if unit_factor > 0 else 1.0)

    lines = [s for s in wall_segments if s.get("entity_type") == "LINE" and len(s.get("points", [])) == 2]
    other = [s for s in wall_segments if s.get("entity_type") != "LINE" or len(s.get("points", [])) != 2]

    matched_indices = set()
    deduped_lines = []

    for i in range(len(lines)):
        if i in matched_indices:
            continue
        p1, p2 = lines[i]["points"]
        match_found = False

        for j in range(i + 1, len(lines)):
            if j in matched_indices:
                continue
            q1, q2 = lines[j]["points"]
            if are_parallel(p1, p2, q1, q2):
                perp_d = offset_distance(p1, p2, q1, q2)
                if min_dist <= perp_d <= max_dist:
                    matched_indices.add(j)
                    match_found = True
                    center_p1 = [(p1[0] + q1[0]) / 2.0, (p1[1] + q1[1]) / 2.0]
                    center_p2 = [(p2[0] + q2[0]) / 2.0, (p2[1] + q2[1]) / 2.0]
                    merged = dict(lines[i])
                    merged["points"] = [center_p1, center_p2]
                    merged["length"] = distance_point_to_point(center_p1, center_p2)
                    merged["thickness"] = perp_d
                    merged["paired_handle"] = lines[j].get("handle")
                    _add_bounds(merged)
                    deduped_lines.append(merged)
                    break

        if not match_found:
            deduped_lines.append(lines[i])

    return deduped_lines + other
