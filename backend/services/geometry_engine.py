import math
import re
from collections import defaultdict, Counter


PATTERNS = {
    "Walls": [r"\bwall\b", r"\bwalls\b", r"a[-_ ]?wall", r"masonry", r"brick", r"aac", r"block", r"partition"],
    "Doors": [r"\bdoor\b", r"\bdoors\b", r"a[-_ ]?door", r"door[-_ ]?tag", r"\bdr[-_ ]?\d"],
    "Windows": [r"\bwindow\b", r"\bwindows\b", r"a[-_ ]?window", r"glazing", r"\bwin[-_ ]?\d"],
    "Columns": [r"\bcolumn\b", r"\bcolumns\b", r"s[-_ ]?column", r"struct[-_ ]?col"],
    "Beams": [r"\bbeam\b", r"\bbeams\b", r"s[-_ ]?beam", r"struct[-_ ]?beam"],
    "Slabs": [r"\bslab\b", r"\bslabs\b", r"floor[-_ ]?slab", r"roof[-_ ]?slab"],
    "Footings": [r"\bfooting\b", r"\bfootings\b", r"foundation", r"\bfnd\b", r"\bpad[-_ ]?foot"],
    "Flooring": [r"\bflooring\b", r"floor[-_ ]?finish", r"\btile\b", r"\btiles\b"],
    "Stairs": [r"\bstair\b", r"\bstairs\b", r"staircase", r"stair[-_ ]?flight"],
}

# Fixed LibreDWG entity codes. These are stable codes from LibreDWG's
# DWG_OBJECT_TYPE enum for the common native entities we need to measure.
TYPE_NAMES = {
    1: "TEXT", 2: "ATTRIB", 3: "ATTDEF", 4: "BLOCK", 5: "ENDBLK", 6: "SEQEND",
    7: "INSERT", 8: "MINSERT", 10: "VERTEX_2D", 11: "VERTEX_3D", 12: "VERTEX_MESH",
    13: "VERTEX_PFACE", 14: "VERTEX_PFACE_FACE", 15: "POLYLINE_2D", 16: "POLYLINE_3D",
    17: "ARC", 18: "CIRCLE", 19: "LINE", 20: "DIMENSION_ORDINATE", 21: "DIMENSION_LINEAR",
    22: "DIMENSION_ALIGNED", 23: "DIMENSION_ANG3PT", 24: "DIMENSION_ANG2LN", 25: "DIMENSION_RADIUS",
    26: "DIMENSION_DIAMETER", 27: "POINT", 28: "3DFACE", 29: "POLYLINE_PFACE", 30: "POLYLINE_MESH",
    31: "SOLID", 32: "TRACE", 33: "SHAPE", 34: "VIEWPORT", 35: "ELLIPSE", 36: "SPLINE",
    37: "REGION", 38: "3DSOLID", 39: "BODY", 40: "RAY", 41: "XLINE", 42: "DICTIONARY",
    43: "OLEFRAME", 44: "MTEXT", 45: "LEADER", 46: "TOLERANCE", 47: "MLINE", 77: "LWPOLYLINE",
    78: "HATCH", 79: "XRECORD",
}

GEOMETRIC_TYPES = {
    "LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE_2D", "POLYLINE_3D",
    "3DFACE", "SOLID", "TRACE", "ELLIPSE", "SPLINE", "MLINE", "HATCH",
}


def _text(x):
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    if isinstance(x, (int, float)):
        return str(x)
    if isinstance(x, list):
        return " ".join(_text(v) for v in x)
    if isinstance(x, dict):
        return " ".join(f"{k} {_text(v)}" for k, v in x.items())
    return str(x)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _point(x):
    if isinstance(x, (list, tuple)) and len(x) >= 2:
        a, b = _num(x[0]), _num(x[1])
        if a is not None and b is not None:
            return (a, b)
    if isinstance(x, dict):
        for a, b in (("x", "y"), ("X", "Y"), ("x_coordinate", "y_coordinate")):
            if a in x and b in x:
                p = _point([x[a], x[b]])
                if p:
                    return p
        for k in ("point", "position", "center", "start", "end", "first_point", "second_point"):
            if k in x:
                p = _point(x[k])
                if p:
                    return p
    return None


def _points(obj):
    if not isinstance(obj, dict):
        return []
    for key in ("points", "vertices", "vertexes", "coords", "coordinates"):
        value = obj.get(key)
        if not isinstance(value, list):
            continue
        out = []
        for item in value:
            p = _point(item)
            if p:
                out.append(p)
        if len(out) >= 2:
            return out
    return []


def _line_from_obj(obj):
    if not isinstance(obj, dict):
        return 0.0
    pairs = [
        ("start", "end"), ("start_point", "end_point"), ("startPoint", "endPoint"),
        ("first_point", "second_point"), ("p1", "p2"), ("point1", "point2"),
    ]
    for a, b in pairs:
        if a in obj and b in obj:
            p1, p2 = _point(obj[a]), _point(obj[b])
            if p1 and p2:
                return math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    for key in ("length", "length_m", "distance"):
        n = _num(obj.get(key))
        if n is not None:
            return abs(n)
    return 0.0


def _poly_length(ps, closed=False):
    total = sum(math.hypot(ps[i][0] - ps[i-1][0], ps[i][1] - ps[i-1][1]) for i in range(1, len(ps)))
    if closed and len(ps) > 2:
        total += math.hypot(ps[0][0] - ps[-1][0], ps[0][1] - ps[-1][1])
    return total


def _poly_area(ps):
    if len(ps) < 3:
        return 0.0
    return abs(sum(ps[i][0] * ps[(i + 1) % len(ps)][1] - ps[(i + 1) % len(ps)][0] * ps[i][1] for i in range(len(ps))) / 2.0)


def _geometry_from_json(obj, type_name):
    if not isinstance(obj, dict):
        return 0.0, 0.0
    if type_name == "LINE":
        return _line_from_obj(obj), 0.0
    if type_name == "CIRCLE":
        r = _num(obj.get("radius"))
        if r is not None:
            return 2 * math.pi * abs(r), math.pi * r * r
    if type_name == "ARC":
        r = _num(obj.get("radius"))
        a1 = _num(obj.get("start_angle"))
        a2 = _num(obj.get("end_angle"))
        if r is not None and a1 is not None and a2 is not None:
            sweep = abs(a2 - a1)
            return abs(r) * sweep, 0.0
    ps = _points(obj)
    if ps:
        closed = bool(obj.get("closed") or obj.get("is_closed") or obj.get("closed_flag"))
        return _poly_length(ps, closed), _poly_area(ps) if closed else 0.0
    for key in ("area", "area_m2"):
        a = _num(obj.get(key))
        if a is not None:
            return _line_from_obj(obj), abs(a)
    return _line_from_obj(obj), 0.0


def _walk_entity_dicts(root):
    """Find likely top-level entity records without counting every nested field."""
    out = []
    seen = set()

    def rec(x):
        if isinstance(x, dict):
            typ = x.get("entity") if x.get("entity") not in (None, "") else x.get("object")
            has_type = "type" in x
            has_index = "index" in x
            if typ not in (None, "") or (has_type and (has_index or "handle" in x)):
                ident = id(x)
                if ident not in seen:
                    seen.add(ident)
                    out.append(x)
            for v in x.values():
                rec(v)
        elif isinstance(x, list):
            for v in x:
                rec(v)
    rec(root)
    return out


def _type_name(obj):
    raw = obj.get("type")
    if isinstance(raw, str):
        s = raw.upper().replace(" ", "_")
        if s in TYPE_NAMES.values():
            return s
        return s
    n = _num(raw)
    if n is not None:
        return TYPE_NAMES.get(int(n), f"TYPE_{int(n)}")
    for k in ("entity", "object", "objecttype", "entity_type"):
        if obj.get(k):
            return str(obj[k]).upper()
    return "UNKNOWN"


def _semantic(blob):
    s = _text(blob).lower()
    scores = {}
    for name, patterns in PATTERNS.items():
        score = 0
        for p in patterns:
            if re.search(p, s, re.I):
                score += 1
        if score:
            scores[name] = score
    return max(scores, key=scores.get) if scores else None


def _blank_stats():
    return {"count": 0, "length": 0.0, "area": 0.0, "layers": set(), "basis": set()}


def _consume(stats, name, count=1, length=0.0, area=0.0, layer=None, basis="metadata"):
    s = stats[name]
    s["count"] += max(0, int(count))
    s["length"] += max(0.0, float(length or 0))
    s["area"] += max(0.0, float(area or 0))
    if layer:
        s["layers"].add(str(layer))
    s["basis"].add(basis)


def _analyze_json(data):
    stats = defaultdict(_blank_stats)
    entity_types = Counter()
    layers = set()
    entities = _walk_entity_dicts(data)
    for obj in entities:
        typ = _type_name(obj)
        entity_types[typ] += 1
        layer = obj.get("layer") or obj.get("layer_name") or obj.get("Layer")
        if layer is not None:
            layers.add(_text(layer))
        # Search string-valued nested fields as well. LibreDWG JSON can put
        # block/text/class metadata several levels below the entity record.
        strings = []
        def collect_strings(x):
            if isinstance(x, str):
                strings.append(x)
            elif isinstance(x, dict):
                for v in x.values(): collect_strings(v)
            elif isinstance(x, list):
                for v in x: collect_strings(v)
        collect_strings(obj)
        blob = " ".join([_text(layer)] + strings)
        semantic = _semantic(blob)
        length, area = _geometry_from_json(obj, typ)
        if semantic:
            # INSERT/text records are strong semantic evidence. Geometry records
            # on a named layer are also useful. This is intentionally not based on
            # filename or a fixed project count.
            _consume(stats, semantic, 1, length, area, layer, "JSON")
    return stats, entity_types, layers, len(entities)


def _features(data):
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("features"), list):
        return [f for f in data["features"] if isinstance(f, dict)]
    out = []
    for v in data.values():
        if isinstance(v, dict) and isinstance(v.get("features"), list):
            out.extend(f for f in v["features"] if isinstance(f, dict))
    return out


def _geo_metrics(g):
    if not isinstance(g, dict):
        return 0.0, 0.0
    typ, c = g.get("type"), g.get("coordinates")
    if typ == "Point":
        return 0.0, 0.0
    if typ == "LineString":
        ps = [_point(x) for x in c or []]; ps = [p for p in ps if p]
        return _poly_length(ps), 0.0
    if typ == "MultiLineString":
        return sum(_geo_metrics({"type":"LineString", "coordinates":x})[0] for x in c or []), 0.0
    if typ == "Polygon":
        if not c: return 0.0, 0.0
        return 0.0, max(0.0, _poly_area([_point(x) for x in c[0] if _point(x)]) - sum(_poly_area([_point(x) for x in r if _point(x)]) for r in c[1:]))
    if typ == "MultiPolygon":
        return 0.0, sum(_geo_metrics({"type":"Polygon","coordinates":p})[1] for p in c or [])
    if typ == "GeometryCollection":
        vals = [_geo_metrics(x) for x in g.get("geometries", [])]
        return sum(x[0] for x in vals), sum(x[1] for x in vals)
    return 0.0, 0.0


def _analyze_geojson(data):
    stats = defaultdict(_blank_stats)
    layers = set()
    features = _features(data)
    for f in features:
        props = f.get("properties") or {}
        layer = props.get("layer") or props.get("Layer") or props.get("layer_name")
        if layer is not None: layers.add(_text(layer))
        semantic = _semantic(props)
        length, area = _geo_metrics(f.get("geometry"))
        if semantic:
            _consume(stats, semantic, 1, length, area, layer, "GeoJSON")
    return stats, layers, len(features)


def analyze_dwg(cad):
    data = cad.get("data", cad) if isinstance(cad, dict) else cad
    json_data = data.get("json") if isinstance(data, dict) else None
    geo_data = data.get("geojson") if isinstance(data, dict) else None

    jstats, etypes, jlayers, jcount = _analyze_json(json_data) if json_data is not None else (defaultdict(_blank_stats), Counter(), set(), 0)
    gstats, glayers, gcount = _analyze_geojson(geo_data) if geo_data is not None else (defaultdict(_blank_stats), set(), 0)

    names = list(PATTERNS.keys())
    elements = []
    for name in names:
        j, g = jstats.get(name), gstats.get(name)
        if not j and not g:
            continue
        # Counts are metadata detections; do not add JSON + GeoJSON copies of the
        # same entity. Geometry prefers GeoJSON because it is explicit geometry.
        count = max(j["count"] if j else 0, g["count"] if g else 0)
        length = (g["length"] if g and g["length"] > 0 else (j["length"] if j else 0))
        area = (g["area"] if g and g["area"] > 0 else (j["area"] if j else 0))
        layers = sorted((j["layers"] if j else set()) | (g["layers"] if g else set()))
        basis = sorted((j["basis"] if j else set()) | (g["basis"] if g else set()))
        elements.append({
            "name": name, "count": int(count), "length_m": round(length, 3),
            "area_m2": round(area, 3), "volume_m3": 0.0, "layers": layers,
            "detection_basis": "+".join(basis) if basis else "metadata",
        })

    notes = []
    if not json_data:
        notes.append("LibreDWG JSON output was unavailable; analysis used geometry output only.")
    if not geo_data:
        notes.append("LibreDWG GeoJSON output was unavailable; length/area may be incomplete.")
    if not elements:
        notes.append("No construction semantics were found in layer/block/text metadata. The drawing may use generic layer names or unsupported/proxy objects.")
    if not any(e["length_m"] or e["area_m2"] for e in elements):
        notes.append("No measurable construction geometry was linked to detected elements; quantities requiring dimensions remain assumptions.")

    diagnostics = cad.get("diagnostics", []) if isinstance(cad, dict) else []
    return {
        "entities": max(jcount, gcount),
        "layers": len(jlayers | glayers),
        "layer_names": sorted(jlayers | glayers),
        "units": _find_units(json_data) or "Unitless (scale must be verified)",
        "element_types": len(elements),
        "elements": elements,
        "entity_types": dict(etypes.most_common(30)),
        "diagnostics": diagnostics,
        "notes": notes,
    }


def _find_units(data):
    if data is None:
        return None
    candidates = []
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                kl = str(k).lower()
                if kl in {"units", "insunits", "$insunits", "drawing_units", "unit"} and v not in (None, ""):
                    candidates.append(_text(v))
                walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(data)
    return candidates[0] if candidates else None
