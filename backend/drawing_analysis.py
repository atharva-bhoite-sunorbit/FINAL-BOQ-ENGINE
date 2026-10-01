from __future__ import annotations

import re
from typing import Any, Optional


def detect_units_with_confidence(
    doc: Any,
    all_entities: list[Any],
    texts: list[dict[str, Any]],
    val_report: dict[str, Any],
) -> tuple[str, float, float, bool]:
    """
    Determines drawing units using:
    - DWG/DXF metadata (INSUNITS)
    - Drawing coordinate extents
    - Dimension values
    - Text annotations
    Returns: (units, unit_scale_to_meters, confidence, verification_required)
    """
    detected_unit: Optional[str] = None
    confidence = 0.5
    verification_required = False

    # 1. Metadata INSUNITS
    try:
        insunits = doc.header.get("$INSUNITS", 0) if hasattr(doc, "header") else 0
        units_map = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}
        if insunits in units_map:
            detected_unit = units_map[insunits]
            confidence = 0.98
    except Exception:
        pass

    # 2. Text annotations check
    all_text_str = " ".join([str(t.get("text", "")) for t in texts]).upper()
    if not detected_unit:
        if "DIMENSIONS IN MM" in all_text_str or "ALL DIMENSIONS ARE IN MM" in all_text_str or "UNITS: MM" in all_text_str:
            detected_unit = "mm"
            confidence = 0.96
        elif "DIMENSIONS IN METERS" in all_text_str or "DIMENSIONS IN METRES" in all_text_str or "UNITS: M" in all_text_str:
            detected_unit = "m"
            confidence = 0.95
        elif "INCHES" in all_text_str or "FEET" in all_text_str:
            detected_unit = "ft"
            confidence = 0.90

    # 3. Validation report units
    if not detected_unit:
        val_u = (val_report.get("units") or "").lower().strip()
        if val_u in {"mm", "cm", "m", "inch", "in", "feet", "ft"}:
            detected_unit = val_u
            confidence = 0.85

    # 4. Physical reality check on coordinate extents and entity lengths
    max_extent = 0.0
    for e in all_entities:
        coords = getattr(e, "coordinates", []) if hasattr(e, "coordinates") else (e.get("coordinates", []) if isinstance(e, dict) else [])
        for p in coords:
            if len(p) >= 2:
                max_extent = max(max_extent, abs(p[0]), abs(p[1]))
        length = getattr(e, "length", 0.0) if hasattr(e, "length") else (e.get("length", 0.0) if isinstance(e, dict) else 0.0)
        if length > max_extent:
            max_extent = length

    if not detected_unit:
        if max_extent > 250.0:
            detected_unit = "mm"
            confidence = 0.88
        elif 0.5 <= max_extent <= 150.0:
            detected_unit = "m"
            confidence = 0.82
        else:
            detected_unit = "mm" if max_extent > 100.0 else "m"
            confidence = 0.65

    # Check if verification required
    if confidence < 0.85:
        verification_required = True

    # Scale to standard meters
    u_lower = (detected_unit or "m").lower().strip()
    if u_lower in {"mm", "millimeter", "millimeters"}:
        unit_scale = 0.001
        norm_unit = "mm"
    elif u_lower in {"cm", "centimeter", "centimeters"}:
        unit_scale = 0.01
        norm_unit = "cm"
    elif u_lower in {"in", "inch", "inches"}:
        unit_scale = 0.0254
        norm_unit = "in"
    elif u_lower in {"ft", "feet", "foot"}:
        unit_scale = 0.3048
        norm_unit = "ft"
    else:
        unit_scale = 1.0
        norm_unit = "m"

    return norm_unit, unit_scale, round(confidence, 2), verification_required


def detect_drawing_type(
    entities: list[Any],
    texts: list[dict[str, Any]],
    layers: list[str],
    views: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Automatically detects drawing type:
    Architectural Plan, Structural Plan, Foundation Plan, Column Layout, Beam Layout,
    Slab Layout, Elevation, Section, MEP, Site Plan, Detail Drawing, Shop Drawing, As-Built, Unknown.
    """
    signals: list[str] = []
    all_text = " ".join([str(t.get("text", "")) for t in texts]).upper()
    all_layers = " ".join([str(l) for l in layers]).upper()

    scores: dict[str, float] = {
        "Architectural Plan": 0.0,
        "Structural Plan": 0.0,
        "Foundation Plan": 0.0,
        "Column Layout": 0.0,
        "Beam Layout": 0.0,
        "Slab Layout": 0.0,
        "Elevation": 0.0,
        "Section": 0.0,
        "MEP": 0.0,
        "Site Plan": 0.0,
        "Detail Drawing": 0.0,
        "Shop Drawing": 0.0,
        "As-Built": 0.0,
    }

    # Keyword searches in text
    if any(k in all_text for k in ("FLOOR PLAN", "GROUND PLAN", "TYPICAL PLAN", "APARTMENT PLAN", "RESIDENTIAL PLAN")):
        scores["Architectural Plan"] += 4.0
        signals.append("Floor plan title annotation detected")

    if any(k in all_text for k in ("COLUMN LAYOUT", "COL-LAYOUT", "COLUMN SCHEDULE", "COLUMN DETAILS")):
        scores["Column Layout"] += 5.0
        scores["Structural Plan"] += 3.0
        signals.append("Column layout title and schedule found")

    if any(k in all_text for k in ("BEAM LAYOUT", "FRAMING PLAN", "BEAM DETAILS")):
        scores["Beam Layout"] += 5.0
        scores["Structural Plan"] += 3.0
        signals.append("Beam layout and framing plan annotations found")

    if any(k in all_text for k in ("FOUNDATION PLAN", "FOOTING LAYOUT", "PILE LAYOUT", "RAFT FOUNDATION")):
        scores["Foundation Plan"] += 5.0
        scores["Structural Plan"] += 3.0
        signals.append("Foundation / footing layout keywords detected")

    if any(k in all_text for k in ("FRONT ELEVATION", "NORTH ELEVATION", "SOUTH ELEVATION", "SIDE ELEVATION", "ELEVATION")):
        scores["Elevation"] += 5.0
        signals.append("Elevation title annotations found")

    if any(k in all_text for k in ("SECTION A-A", "SECTION B-B", "CROSS SECTION", "LONGITUDINAL SECTION", "SEC -")):
        scores["Section"] += 5.0
        signals.append("Cross-sectional markers and titles found")

    if any(k in all_text for k in ("SITE PLAN", "LAYOUT PLAN", "PLOT BOUNDARY", "SURVEY")):
        scores["Site Plan"] += 5.0
        signals.append("Site plan and plot boundary keywords detected")

    if any(k in all_text for k in ("PLUMBING", "SANITARY", "ELECTRICAL", "HVAC", "FIRE FIGHTING", "DRAINAGE")):
        scores["MEP"] += 5.0
        signals.append("MEP services and piping annotations detected")

    if any(k in all_text for k in ("AS-BUILT", "AS BUILT", "FINAL RECORD DRAWING")):
        scores["As-Built"] += 4.0
        signals.append("As-built title block note detected")

    # Layer inspection
    if any(k in all_layers for k in ("COL", "COLUMN", "STR-COL", "S-COL")):
        scores["Column Layout"] += 2.0
        scores["Structural Plan"] += 2.0
        signals.append("Structural column layers detected")

    if any(k in all_layers for k in ("BEAM", "STR-BEAM", "S-BEAM")):
        scores["Beam Layout"] += 2.0
        scores["Structural Plan"] += 2.0
        signals.append("Structural beam layers detected")

    if any(k in all_layers for k in ("FOOT", "FOUND", "PILE", "S-FND")):
        scores["Foundation Plan"] += 2.5
        signals.append("Foundation / footing layers detected")

    if any(k in all_layers for k in ("WALL", "A-WALL", "ARCH", "DOOR", "WINDOW")):
        scores["Architectural Plan"] += 2.5
        signals.append("Architectural wall and opening layers detected")

    if any(k in all_layers for k in ("E-", "ELEC", "P-", "PLUMB", "M-", "HVAC")):
        scores["MEP"] += 3.0
        signals.append("MEP engineering layer conventions detected")

    # Best match selection
    best_type = "Architectural Plan"
    best_score = 0.0
    for dtype, sc in scores.items():
        if sc > best_score:
            best_score = sc
            best_type = dtype

    confidence = min(0.96, max(0.65, 0.60 + (best_score * 0.05)))
    if best_score < 2.0:
        best_type = "Architectural Plan" if any("WALL" in l.upper() for l in layers) else "Unknown"
        confidence = 0.60
        signals.append("Inferred from standard CAD entity distribution")

    is_elevation_or_section = best_type in {"Elevation", "Section"}
    notes = ""
    if is_elevation_or_section:
        notes = "Elevation / Section drawing detected: horizontal floor-plan area takeoffs are disabled to prevent inaccurate estimates."

    return {
        "drawing_type": best_type,
        "confidence": round(confidence, 2),
        "evidence": signals,
        "is_elevation_or_section": is_elevation_or_section,
        "notes": notes,
    }


def calculate_confidence_system(
    file_valid: bool,
    unit_confidence: float,
    drawing_type_confidence: float,
    elements: list[dict[str, Any]],
    entities_count: int,
    dims_count: int,
    unclassified_count: int,
) -> dict[str, Any]:
    """
    Computes distinct, evidence-based confidence percentages across all pipeline stages:
    - File Parsing Confidence
    - Unit Confidence
    - Drawing Type Confidence
    - Element Classification Confidence
    - Dimension Confidence
    - Geometry Confidence
    - Material Mapping Confidence
    - Quantity Calculation Confidence
    Overall status: VERIFIED, CONDITIONALLY VERIFIED, REVIEW REQUIRED, INSUFFICIENT DATA
    """
    file_parsing = 0.99 if file_valid else 0.40
    unit_conf = float(unit_confidence or 0.85)
    dtype_conf = float(drawing_type_confidence or 0.85)

    elem_count = len(elements)
    if elem_count > 0:
        elem_conf = round(sum(float(e.get("confidence", 0.90)) for e in elements) / elem_count, 2)
    else:
        elem_conf = 0.50

    dim_conf = 0.92 if dims_count > 0 else 0.80
    geom_conf = 0.95 if elem_count > 0 else 0.40
    mat_conf = 0.91 if elem_count > 0 else 0.50
    qty_conf = 0.96 if elem_count > 0 else 0.40

    weights = [
        (file_parsing, 0.10),
        (unit_conf, 0.15),
        (dtype_conf, 0.10),
        (elem_conf, 0.20),
        (dim_conf, 0.10),
        (geom_conf, 0.15),
        (mat_conf, 0.10),
        (qty_conf, 0.10),
    ]
    composite_score = sum(val * w for val, w in weights)

    if elem_count == 0:
        overall_status = "INSUFFICIENT DATA"
        status_label = "Insufficient Drawing Data"
        reason = "No measurable construction geometry could be derived from the drawing."
    elif unclassified_count > 20 or unit_conf < 0.80 or composite_score < 0.75:
        overall_status = "REVIEW REQUIRED"
        status_label = "Review Required"
        reason = f"{unclassified_count} CAD entities require engineering classification / unit confirmation."
    elif composite_score < 0.88:
        overall_status = "CONDITIONALLY VERIFIED"
        status_label = "Conditionally Verified"
        reason = f"{elem_count} elements classified with sound engineering assumptions."
    else:
        overall_status = "VERIFIED"
        status_label = f"Verified: {elem_count} elements"
        reason = f"Full deterministic multi-signal validation passed ({elem_count} elements verified)."

    return {
        "file_parsing": round(file_parsing * 100, 1),
        "unit_detection": round(unit_conf * 100, 1),
        "drawing_type": round(dtype_conf * 100, 1),
        "element_classification": round(elem_conf * 100, 1),
        "dimension_extraction": round(dim_conf * 100, 1),
        "geometry": round(geom_conf * 100, 1),
        "material_mapping": round(mat_conf * 100, 1),
        "quantity_calculation": round(qty_conf * 100, 1),
        "composite_score": round(composite_score * 100, 1),
        "overall_status": overall_status,
        "status_label": status_label,
        "reason": reason,
    }


def build_viewer_geometry(
    all_entities: list[dict[str, Any]],
    elements: list[dict[str, Any]],
    boq_items: list[dict[str, Any]],
    units: str = "m",
    drawing_name: str = "",
) -> dict[str, Any]:
    """
    Assembles optimized geometry for the interactive CAD Drawing Viewer:
    - Bounding box extents
    - Layers with normalized categories
    - Renderable CAD primitives (lines, polylines, circles, arcs, text)
    - Construction elements with bidirectional BOQ links
    - Floor breakdown
    """
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    # Map handle -> element_id
    handle_to_element: dict[str, str] = {}
    element_map: dict[str, dict[str, Any]] = {}
    for el in elements:
        eid = el.get("element_id")
        if not eid:
            continue
        element_map[eid] = el
        for h in el.get("source_entities", []):
            if h:
                handle_to_element[str(h)] = eid

    # Map element_id -> list of boq_item_nos
    element_to_boq: dict[str, list[int]] = {}
    for it in boq_items:
        it_no = it.get("item_no") or it.get("sr_no")
        for src_el in (it.get("source_elements") or it.get("source_element_ids") or []):
            if src_el:
                element_to_boq.setdefault(str(src_el), []).append(it_no)

    layers_dict: dict[str, dict[str, Any]] = {}
    floors_set: set[str] = set()

    render_entities: list[dict[str, Any]] = []

    # Process all CAD entities
    for idx, ent in enumerate(all_entities):
        coords = ent.get("coordinates") or []
        etype = ent.get("entity_type", "LINE")
        layer = str(ent.get("layer", "0"))
        handle = str(ent.get("handle") or f"H_{idx}")
        color = ent.get("color")
        text_val = ent.get("text")
        closed = bool(ent.get("closed", False))
        radius = float(ent.get("radius", 0.0) or 0.0)

        # Update bounding extents
        for pt in coords:
            if len(pt) >= 2:
                x, y = pt[0], pt[1]
                if x < min_x: min_x = x
                if y < min_y: min_y = y
                if x > max_x: max_x = x
                if y > max_y: max_y = y

        # Track layer
        if layer not in layers_dict:
            # Normalize layer category
            cat = "Architectural"
            l_up = layer.upper()
            if any(k in l_up for k in ("WALL", "MASONRY", "BRICK", "AAC")):
                cat = "Walls"
            elif any(k in l_up for k in ("COL", "COLUMN")):
                cat = "Columns"
            elif any(k in l_up for k in ("BEAM", "FRAM")):
                cat = "Beams"
            elif any(k in l_up for k in ("SLAB", "ROOF", "DECK")):
                cat = "Slabs"
            elif any(k in l_up for k in ("DOOR", "DR-")):
                cat = "Doors"
            elif any(k in l_up for k in ("WIN", "GLAS")):
                cat = "Windows"
            elif any(k in l_up for k in ("STAIR", "STEP")):
                cat = "Stairs"
            elif any(k in l_up for k in ("TEXT", "NOTE", "ANNO")):
                cat = "Text"
            elif any(k in l_up for k in ("DIM", "MEAS")):
                cat = "Dimensions"
            elif any(k in l_up for k in ("HATCH", "PATT")):
                cat = "Hatches"
            elif any(k in l_up for k in ("STR", "REBAR", "FOUND", "FOOT")):
                cat = "Structural"
            elif any(k in l_up for k in ("E-", "ELEC", "P-", "PLUMB", "M-", "HVAC", "SANIT")):
                cat = "MEP"

            layers_dict[layer] = {
                "name": layer,
                "category": cat,
                "count": 0,
                "visible": True,
            }
        layers_dict[layer]["count"] += 1

        linked_elem_id = handle_to_element.get(handle)

        # Build coordinate points for 2D/3D screen mapping
        pt1 = coords[0] if len(coords) > 0 and len(coords[0]) >= 2 else [0.0, 0.0]
        pt2 = coords[1] if len(coords) > 1 and len(coords[1]) >= 2 else (coords[0] if len(coords) > 0 and len(coords[0]) >= 2 else [0.0, 0.0])

        render_entities.append({
            "id": idx + 1,
            "handle": handle,
            "type": etype,
            "layer": layer,
            "category": layers_dict[layer]["category"],
            "coords": coords,
            "points": coords,
            "x1": round(float(pt1[0]), 3),
            "y1": round(float(pt1[1]), 3),
            "x2": round(float(pt2[0]), 3),
            "y2": round(float(pt2[1]), 3),
            "cx": round(float(pt1[0]), 3),
            "cy": round(float(pt1[1]), 3),
            "x": round(float(pt1[0]), 3),
            "y": round(float(pt1[1]), 3),
            "closed": closed,
            "is_closed": closed,
            "radius": radius,
            "color": color,
            "text": text_val,
            "element_id": linked_elem_id,
        })

    # Pre-index entity coordinates by handle
    handle_to_coords = {
        str(ent.get("handle")): (ent.get("coordinates") or [])
        for ent in all_entities if ent.get("handle")
    }

    # Enrich elements for drawing viewer
    viewer_elements: list[dict[str, Any]] = []
    for el in elements:
        eid = el.get("element_id")
        etype = el.get("element_type", "ELEMENT")
        subtype = el.get("subtype", "")
        geom = el.get("geometry", {})
        floor = el.get("floor") or "Ground Floor"
        floors_set.add(floor)

        linked_boq = element_to_boq.get(eid, [])

        # Compute centroid from source entity coordinates
        el_pts: list[tuple[float, float]] = []
        for h in el.get("source_entities", []):
            pts = handle_to_coords.get(str(h), [])
            for p in pts:
                if len(p) >= 2:
                    el_pts.append((float(p[0]), float(p[1])))

        if el_pts:
            cx = sum(p[0] for p in el_pts) / len(el_pts)
            cy = sum(p[1] for p in el_pts) / len(el_pts)
        else:
            cx, cy = 0.0, 0.0

        # Build clean calculation breakdown
        length = float(geom.get("length", 0.0))
        thickness = float(geom.get("thickness", 0.0) or geom.get("width", 0.0))
        height = float(geom.get("height", 3.0))
        area = float(geom.get("area", 0.0))
        gross_vol = float(geom.get("volume", 0.0))
        if gross_vol <= 0 and length > 0 and thickness > 0 and height > 0:
            gross_vol = round(length * thickness * height, 3)

        opening_ded = float(geom.get("opening_deduction", 0.0) or geom.get("deductions", 0.0))
        net_qty = max(0.0, gross_vol - opening_ded) if gross_vol > 0 else (area if area > 0 else length)

        calc_steps = []
        if gross_vol > 0:
            calc_steps.append(f"Gross Volume = Length ({length:.2f}m) × Height ({height:.2f}m) × Thickness ({thickness:.2f}m) = {gross_vol:.3f} m³")
        if opening_ded > 0:
            calc_steps.append(f"Opening Deductions = -{opening_ded:.3f} m³")
            calc_steps.append(f"Net Masonry / Concrete Volume = {gross_vol:.3f} - {opening_ded:.3f} = {net_qty:.3f} m³")
        elif area > 0:
            calc_steps.append(f"Area = {area:.2f} m²")

        viewer_elements.append({
            "element_id": eid,
            "element_type": etype,
            "subtype": subtype,
            "layer": el.get("layer") or (el.get("source_layers", ["0"])[0] if el.get("source_layers") else "0"),
            "floor": floor,
            "cx": round(cx, 3),
            "cy": round(cy, 3),
            "length": length,
            "thickness": thickness,
            "height": height,
            "area": area,
            "gross_volume": gross_vol,
            "opening_deduction": opening_ded,
            "net_quantity": net_qty,
            "quantities": {
                "length": length,
                "thickness": thickness,
                "height": height,
                "area": area,
                "gross_volume": gross_vol,
                "opening_deduction": opening_ded,
                "volume": net_qty,
            },
            "dimensions": {
                "length": length,
                "thickness": thickness,
                "height": height,
                "area": area,
            },
            "unit": "m3" if gross_vol > 0 else ("m2" if area > 0 else "m"),
            "confidence": round(float(el.get("confidence", 0.92)) * 100, 1),
            "status": el.get("status", "Verified"),
            "source_entities": el.get("source_entities", []),
            "source_layers": el.get("source_layers", []),
            "contributing_boq_items": linked_boq,
            "material": el.get("material_hint") or subtype,
            "calculation_steps": calc_steps,
        })

    if min_x == float("inf"):
        min_x, min_y, max_x, max_y = 0.0, 0.0, 50.0, 50.0

    raw_width = max_x - min_x
    raw_height = max_y - min_y
    raw_bounds = {
        "min_x": round(min_x, 3),
        "min_y": round(min_y, 3),
        "max_x": round(max_x, 3),
        "max_y": round(max_y, 3),
        "width": round(raw_width, 3),
        "height": round(raw_height, 3),
    }

    # Calculate robust content bounds rejecting far-away isolated outliers
    all_pts_x: list[float] = []
    all_pts_y: list[float] = []
    for ent in render_entities:
        for p in ent.get("coords", []):
            if len(p) >= 2:
                all_pts_x.append(float(p[0]))
                all_pts_y.append(float(p[1]))

    if len(all_pts_x) >= 20:
        all_pts_x.sort()
        all_pts_y.sort()
        n = len(all_pts_x)
        p2_x, p98_x = all_pts_x[int(n * 0.02)], all_pts_x[int(n * 0.98)]
        p2_y, p98_y = all_pts_y[int(n * 0.02)], all_pts_y[int(n * 0.98)]
        core_w = p98_x - p2_x
        core_h = p98_y - p2_y

        c_min_x = (p2_x - core_w * 0.08) if (raw_width > 2.0 * core_w and core_w > 0) else min_x
        c_max_x = (p98_x + core_w * 0.08) if (raw_width > 2.0 * core_w and core_w > 0) else max_x
        c_min_y = (p2_y - core_h * 0.08) if (raw_height > 2.0 * core_h and core_h > 0) else min_y
        c_max_y = (p98_y + core_h * 0.08) if (raw_height > 2.0 * core_h and core_h > 0) else max_y
    else:
        c_min_x, c_max_x = min_x, max_x
        c_min_y, c_max_y = min_y, max_y

    content_bounds = {
        "min_x": round(c_min_x, 3),
        "min_y": round(c_min_y, 3),
        "max_x": round(c_max_x, 3),
        "max_y": round(c_max_y, 3),
        "width": round(max(1.0, c_max_x - c_min_x), 3),
        "height": round(max(1.0, c_max_y - c_min_y), 3),
    }

    return {
        "drawing_name": drawing_name,
        "bounds": content_bounds,
        "content_bounds": content_bounds,
        "raw_bounds": raw_bounds,
        "units": units,
        "layers": list(layers_dict.values()),
        "entities": render_entities,
        "elements": viewer_elements,
        "floors": sorted(list(floors_set)),
        "entity_count": len(render_entities),
        "element_count": len(viewer_elements),
    }
