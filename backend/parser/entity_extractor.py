from __future__ import annotations

import math
from typing import Any
from backend.models.cad_entity import CADEntity


def extract_cad_entities(doc, source_filename: str = "") -> list[CADEntity]:
    entities: list[CADEntity] = []
    entity_counter = 1

    for e in doc.modelspace():
        e_type = e.dxftype()
        handle = getattr(e.dxf, "handle", f"H{entity_counter}")
        layer = getattr(e.dxf, "layer", "0")
        color = getattr(e.dxf, "color", None)
        linetype = getattr(e.dxf, "linetype", None)

        cad_e = CADEntity(
            entity_id=f"E{entity_counter:04d}",
            entity_type=e_type,
            layer=layer,
            handle=handle,
            color=color,
            linetype=linetype,
            source_file=source_filename,
            status="CLASSIFIED",
        )
        entity_counter += 1

        try:
            if e_type == "LINE":
                p1 = [float(e.dxf.start.x), float(e.dxf.start.y)]
                p2 = [float(e.dxf.end.x), float(e.dxf.end.y)]
                cad_e.coordinates = [p1, p2]
                cad_e.length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                _set_bbox(cad_e, [p1, p2])

            elif e_type in {"LWPOLYLINE", "POLYLINE"}:
                if e_type == "LWPOLYLINE":
                    pts = [[float(p[0]), float(p[1])] for p in e.get_points("xy") if len(p) >= 2]
                else:
                    pts = [[float(v.dxf.location.x), float(v.dxf.location.y)] for v in e.vertices]
                closed = bool(getattr(e, "closed", False) or getattr(e.dxf, "flags", 0) & 1)
                cad_e.coordinates = pts
                cad_e.closed = closed
                cad_e.length = _polyline_len(pts, closed)
                cad_e.area = _shoelace(pts) if (closed or len(pts) >= 3) else 0.0
                _set_bbox(cad_e, pts)

            elif e_type == "CIRCLE":
                cx = float(e.dxf.center.x)
                cy = float(e.dxf.center.y)
                r = float(e.dxf.radius)
                cad_e.coordinates = [[cx, cy]]
                cad_e.length = 2 * math.pi * r
                cad_e.area = math.pi * (r ** 2)
                cad_e.bounding_box = {"min_x": cx - r, "min_y": cy - r, "max_x": cx + r, "max_y": cy + r}
                cad_e.extra_properties["radius"] = r

            elif e_type == "ARC":
                cx = float(e.dxf.center.x)
                cy = float(e.dxf.center.y)
                r = float(e.dxf.radius)
                sa = float(getattr(e.dxf, "start_angle", 0))
                ea = float(getattr(e.dxf, "end_angle", 360))
                sweep = math.radians((ea - sa) % 360)
                cad_e.coordinates = [[cx, cy]]
                cad_e.length = abs(r * sweep)
                cad_e.bounding_box = {"min_x": cx - r, "min_y": cy - r, "max_x": cx + r, "max_y": cy + r}
                cad_e.extra_properties.update({"radius": r, "start_angle": sa, "end_angle": ea})

            elif e_type == "ELLIPSE":
                cx = float(e.dxf.center.x)
                cy = float(e.dxf.center.y)
                maj = e.dxf.major_axis
                maj_len = math.hypot(float(maj.x), float(maj.y))
                ratio = float(e.dxf.ratio)
                min_len = maj_len * ratio
                cad_e.coordinates = [[cx, cy]]
                cad_e.area = math.pi * maj_len * min_len
                cad_e.length = math.pi * (3 * (maj_len + min_len) - math.sqrt((3 * maj_len + min_len) * (maj_len + 3 * min_len)))
                _set_bbox(cad_e, [[cx - maj_len, cy - min_len], [cx + maj_len, cy + min_len]])

            elif e_type == "SPLINE":
                pts = []
                if hasattr(e, "control_points") and e.control_points:
                    pts = [[float(p[0]), float(p[1])] for p in e.control_points if len(p) >= 2]
                elif hasattr(e, "fit_points") and e.fit_points:
                    pts = [[float(p[0]), float(p[1])] for p in e.fit_points if len(p) >= 2]
                cad_e.coordinates = pts
                cad_e.closed = bool(getattr(e, "closed", False))
                cad_e.length = _polyline_len(pts, cad_e.closed)
                _set_bbox(cad_e, pts)

            elif e_type == "HATCH":
                h_area, h_pts = _extract_hatch_data(e)
                cad_e.area = h_area
                cad_e.coordinates = h_pts
                _set_bbox(cad_e, h_pts)

            elif e_type == "INSERT":
                bx = float(e.dxf.insert.x)
                by = float(e.dxf.insert.y)
                cad_e.coordinates = [[bx, by]]
                cad_e.block_name = getattr(e.dxf, "name", None)
                cad_e.rotation = float(getattr(e.dxf, "rotation", 0) or 0)
                cad_e.scale = [
                    float(getattr(e.dxf, "xscale", 1) or 1),
                    float(getattr(e.dxf, "yscale", 1) or 1),
                    float(getattr(e.dxf, "zscale", 1) or 1),
                ]
                attribs = {}
                if hasattr(e, "attribs"):
                    for at in e.attribs:
                        attribs[at.dxf.tag] = at.dxf.text
                cad_e.extra_properties["attributes"] = attribs
                cad_e.bounding_box = {"min_x": bx, "min_y": by, "max_x": bx, "max_y": by}

            elif e_type in {"TEXT", "MTEXT"}:
                tx = float(e.dxf.insert.x)
                ty = float(e.dxf.insert.y)
                text_content = e.plain_text() if e_type == "MTEXT" else getattr(e.dxf, "text", "")
                cad_e.coordinates = [[tx, ty]]
                cad_e.text = text_content
                cad_e.rotation = float(getattr(e.dxf, "rotation", 0) or 0)
                cad_e.extra_properties["height"] = float(getattr(e.dxf, "height", 0) or 0)
                cad_e.bounding_box = {"min_x": tx, "min_y": ty, "max_x": tx, "max_y": ty}

            elif e_type == "DIMENSION":
                cad_e.text = getattr(e.dxf, "text", "") or ""
                meas = None
                for attr in ("actual_measurement", "measurement"):
                    val = getattr(e.dxf, attr, None)
                    if val is not None:
                        try:
                            meas = float(val)
                            break
                        except Exception:
                            pass
                cad_e.dimension_value = meas
                if hasattr(e.dxf, "defpoint"):
                    dp = [float(e.dxf.defpoint.x), float(e.dxf.defpoint.y)]
                    cad_e.coordinates = [dp]
                    _set_bbox(cad_e, [dp])

            elif e_type in {"SOLID", "TRACE", "3DFACE"}:
                pts = []
                for p_attr in ("vtx0", "vtx1", "vtx2", "vtx3"):
                    if hasattr(e.dxf, p_attr):
                        v = getattr(e.dxf, p_attr)
                        pts.append([float(v.x), float(v.y)])
                cad_e.coordinates = pts
                cad_e.closed = True
                cad_e.area = _shoelace(pts) if len(pts) >= 3 else 0.0
                _set_bbox(cad_e, pts)

            elif e_type == "POINT":
                px = float(e.dxf.location.x)
                py = float(e.dxf.location.y)
                cad_e.coordinates = [[px, py]]
                cad_e.bounding_box = {"min_x": px, "min_y": py, "max_x": px, "max_y": py}

            elif e_type in {"LEADER", "MLEADER"}:
                pts = []
                if hasattr(e, "vertices"):
                    pts = [[float(v.x), float(v.y)] for v in e.vertices]
                cad_e.coordinates = pts
                cad_e.length = _polyline_len(pts, False)
                _set_bbox(cad_e, pts)

            elif e_type == "OLE2FRAME":
                cad_e.status = "CLASSIFIED"
                cad_e.extra_properties["is_ole"] = True

            else:
                # Store unknown entities as UNCLASSIFIED rather than discarding
                cad_e.status = "UNCLASSIFIED"

        except Exception as err:
            cad_e.status = "UNCLASSIFIED"
            cad_e.extra_properties["parse_warning"] = str(err)

        entities.append(cad_e)

    return entities


def _polyline_len(pts: list[list[float]], closed: bool) -> float:
    if len(pts) < 2:
        return 0.0
    tot = sum(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) for p1, p2 in zip(pts, pts[1:]))
    if closed and len(pts) > 2:
        tot += math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
    return tot


def _shoelace(pts: list[list[float]]) -> float:
    if len(pts) < 3:
        return 0.0
    area = 0.0
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def _extract_hatch_data(hatch) -> tuple[float, list[list[float]]]:
    area = 0.0
    all_pts: list[list[float]] = []
    try:
        if hasattr(hatch, "paths") and hatch.paths:
            for p in hatch.paths:
                pts: list[list[float]] = []
                if hasattr(p, "vertices") and p.vertices:
                    pts = [[float(v[0]), float(v[1])] for v in p.vertices if len(v) >= 2]
                elif hasattr(p, "edges") and p.edges:
                    for ed in p.edges:
                        if hasattr(ed, "start"):
                            pts.append([float(ed.start.x), float(ed.start.y)])
                        if hasattr(ed, "end"):
                            pts.append([float(ed.end.x), float(ed.end.y)])
                if len(pts) >= 3:
                    area += _shoelace(pts)
                    all_pts.extend(pts)
        if area <= 0.0 and hasattr(hatch, "dxf"):
            area = float(getattr(hatch.dxf, "area", 0.0) or 0.0)
    except Exception:
        pass
    return area, all_pts


def _set_bbox(cad_e: CADEntity, pts: list[list[float]]):
    if not pts:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cad_e.bounding_box = {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
    }
