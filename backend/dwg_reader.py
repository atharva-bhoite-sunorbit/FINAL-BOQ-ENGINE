from __future__ import annotations

import io
import math
import os
import shutil
import subprocess
import tempfile
import winreg
from pathlib import Path
from typing import Any, Optional

import ezdxf

from backend.geometry_engine import (
    entity_record,
    normalize_length,
    normalize_area,
    calculate_bounding_box,
    calculate_area,
    _shoelace,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BOQ_TEMP_DIR = REPO_ROOT / "backend" / "temp"
BOQ_TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(BOQ_TEMP_DIR)
os.environ["TEMP"] = str(BOQ_TEMP_DIR)
os.environ["TMP"] = str(BOQ_TEMP_DIR)


# =====================================================================
# 1. INPUT & DWG CONVERSION (Section 1)
# =====================================================================

def get_converter_executable() -> Optional[str]:
    """
    Returns path to ODA File Converter or LibreDWG from environment or system.
    Strictly adheres to Section 1: Reads DWG_CONVERTER_PATH from environment.
    Never hard-codes the converter path.
    """
    # 1. Environment variable DWG_CONVERTER_PATH (primary requirement)
    env_conv = os.environ.get("DWG_CONVERTER_PATH") or os.environ.get("BOQ_DWG_CONVERTER")
    if env_conv and Path(env_conv).exists():
        return str(Path(env_conv))

    # 2. LibreDWG environment variable
    libredwg_env = os.environ.get("BOQ_LIBREDWG_CONVERTER")
    if libredwg_env and Path(libredwg_env).exists():
        return str(Path(libredwg_env))

    # 3. System PATH lookup
    for name in ("ODAFileConverter", "TeighaFileConverter", "dwg2dxf", "dwgread"):
        w = shutil.which(name)
        if w:
            return w

    # 4. Standard Windows Registry / Program Files lookup
    oda = _find_oda_in_registry_or_program_files()
    if oda:
        return str(oda)

    # 5. Bundled repository tools (LibreDWG)
    bundled = [
        REPO_ROOT / "tools libre" / "dwg2dxf.exe",
        REPO_ROOT / "tools libre" / "dwgread.exe",
        REPO_ROOT / "tools" / "LibreDWG" / "dwg2dxf.exe",
    ]
    for b in bundled:
        if b.exists():
            return str(b)

    return None


def converter_status() -> dict[str, Any]:
    path = get_converter_executable()
    return {"available": bool(path), "path": path}


def convert_dwg_to_dxf(path: Path) -> Path:
    """
    Converts DWG to DXF using configured ODA File Converter or LibreDWG.
    If input is already a DXF, skips conversion immediately.
    """
    if path.suffix.lower() == ".dxf":
        return path

    if path.suffix.lower() != ".dwg":
        raise ValueError(f"Unsupported file format '{path.suffix}'. Expected .dwg or .dxf.")

    converter = get_converter_executable()
    if not converter:
        raise RuntimeError(
            "DWG conversion tool not found. Configure DWG_CONVERTER_PATH in environment, "
            "install ODA File Converter, or upload a DXF file directly."
        )

    work_dir = Path(tempfile.mkdtemp(prefix="boq-dwg-", dir=BOQ_TEMP_DIR))
    input_dir = work_dir / "input"
    output_dir = work_dir / "output"
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    input_file = input_dir / path.name
    shutil.copy2(path, input_file)
    out_file = output_dir / f"{path.stem}.dxf"

    conv_name = Path(converter).name.lower()

    if "dwg2dxf" in conv_name:
        cmd = [converter, "-y", "-o", str(out_file), str(input_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if not out_file.exists() or out_file.stat().st_size == 0:
            for extra_flag in (["--as", "r2018"], ["--as", "r2000"], ["-m"]):
                retry_cmd = [converter, "-y", *extra_flag, "-o", str(out_file), str(input_file)]
                subprocess.run(retry_cmd, capture_output=True, text=True, check=False)
                if out_file.exists() and out_file.stat().st_size > 0:
                    break

        if not out_file.exists() or out_file.stat().st_size == 0:
            dwgread = Path(converter).parent / "dwgread.exe"
            if dwgread.exists():
                cmd_read = [str(dwgread), "-O", "DXF", "-o", str(out_file), str(input_file)]
                res_read = subprocess.run(cmd_read, capture_output=True, text=True, check=False)
                if not out_file.exists() or out_file.stat().st_size == 0:
                    raise RuntimeError(f"DWG conversion failed with dwg2dxf/dwgread: {result.stderr or res_read.stderr}")
            else:
                raise RuntimeError(f"dwg2dxf failed to produce valid DXF: {result.stderr or result.stdout}")
    elif "dwgread" in conv_name:
        cmd = [converter, "-O", "DXF", "-o", str(out_file), str(input_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not out_file.exists():
            raise RuntimeError(f"dwgread failed: {result.stderr or result.stdout}")
    else:
        # Standard ODA File Converter CLI
        cmd = [converter, str(input_dir), str(output_dir), "ACAD2018", "DXF", "0", "1"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"ODA File Converter failed: {result.stderr}")
        if not out_file.exists():
            candidates = list(output_dir.glob("*.dxf"))
            if candidates:
                out_file = candidates[0]

    if not out_file.exists() or out_file.stat().st_size == 0:
        raise RuntimeError("DWG conversion completed without producing a valid DXF file.")

    return out_file


def _find_oda_in_registry_or_program_files() -> Optional[Path]:
    for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if root:
            for cand in (
                Path(root) / "ODA" / "ODAFileConverter" / "ODAFileConverter.exe",
                Path(root) / "ODAFileConverter" / "ODAFileConverter.exe",
            ):
                if cand.exists():
                    return cand
    try:
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for key_path in (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ):
                with winreg.OpenKey(hive, key_path) as root:
                    for index in range(winreg.QueryInfoKey(root)[0]):
                        sub_name = winreg.EnumKey(root, index)
                        with winreg.OpenKey(root, sub_name) as sub:
                            name = winreg.QueryValueEx(sub, "DisplayName")[0]
                            if "ODAFileConverter" in str(name):
                                src = winreg.QueryValueEx(sub, "InstallSource")[0]
                                candidate = Path(src) / "ODAFileConverter.exe"
                                if candidate.exists():
                                    return candidate
    except (FileNotFoundError, OSError):
        pass
    return None


# =====================================================================
# 2. DWG/DXF VALIDATION (Section 2)
# =====================================================================

def validate_and_inspect_drawing(file_path: Path) -> dict[str, Any]:
    """
    Validates file existence, extension, openability, detects version, model/paper space,
    units, extents, 2D/3D state, and returns the Section 2 structured report.
    """
    report: dict[str, Any] = {
        "file_name": file_path.name,
        "file_type": "DWG" if file_path.suffix.lower() == ".dwg" else "DXF",
        "converted_to_dxf": False,
        "units": "mm",
        "acad_version": "UNKNOWN",
        "has_model_space": False,
        "paper_spaces": [],
        "is_3d": False,
        "extents": None,
        "entities_found": 0,
        "layers_found": 0,
        "blocks_found": 0,
        "texts_found": 0,
        "dimensions_found": 0,
        "hatches_found": 0,
        "warnings": [],
        "errors": [],
    }

    # 1. Validate file existence
    if not file_path.exists():
        report["errors"].append(f"File not found: {file_path}")
        return report

    # 2. Validate file extension
    ext = file_path.suffix.lower()
    if ext not in {".dwg", ".dxf"}:
        report["errors"].append(f"Invalid file extension '{ext}'. Only .dwg and .dxf are supported.")
        return report

    # 3. Convert if DWG
    dxf_path = file_path
    if ext == ".dwg":
        try:
            dxf_path = convert_dwg_to_dxf(file_path)
            report["converted_to_dxf"] = True
        except Exception as exc:
            report["errors"].append(f"DWG conversion error: {exc}")
            return report

    # 4. Open and inspect document with recovery
    doc = None
    try:
        try:
            doc = ezdxf.readfile(dxf_path)
        except Exception as e1:
            try:
                raw_text = dxf_path.read_text(encoding="utf-8", errors="ignore")
                sanitized = _repair_dxf_tags(raw_text)
                doc = ezdxf.read(io.StringIO(sanitized))
                report["warnings"].append("DXF tags were sanitized and recovered.")
            except Exception:
                from ezdxf import recover
                doc, auditor = recover.readfile(dxf_path)
                if auditor.has_errors:
                    report["warnings"].append("Document recovered using ezdxf recovery mode.")
    except Exception as exc:
        report["errors"].append(f"Unable to read or parse DXF document: {exc}")
        return report

    if doc is None:
        report["errors"].append("Failed to load document via CAD parser.")
        return report

    # 5. Version detection
    try:
        acad_ver = doc.header.get("$ACADVER", "UNKNOWN")
        version_names = {
            "AC1015": "AutoCAD 2000",
            "AC1018": "AutoCAD 2004",
            "AC1021": "AutoCAD 2007",
            "AC1024": "AutoCAD 2010",
            "AC1027": "AutoCAD 2013",
            "AC1032": "AutoCAD 2018+",
        }
        report["acad_version"] = version_names.get(acad_ver, acad_ver)
    except Exception:
        pass

    # 6. Spaces detection
    try:
        report["has_model_space"] = bool(doc.modelspace())
        report["paper_spaces"] = [layout.name for layout in doc.layouts if layout.name != "Model"]
    except Exception:
        pass

    # 7. Units detection
    units = _units_from_header(doc)
    report["units"] = units

    # 8. Coordinate Extents & 2D/3D check
    try:
        msp = doc.modelspace()
        all_entities = list(msp)
        report["entities_found"] = len(all_entities)

        report["layers_found"] = len(list(doc.layers)) if hasattr(doc, "layers") else 0
        report["blocks_found"] = len(list(doc.blocks)) if hasattr(doc, "blocks") else 0

        texts = 0
        dims = 0
        hatches = 0
        has_3d = False
        all_pts: list[list[float]] = []

        for e in all_entities:
            dxftype = e.dxftype()
            if dxftype in {"TEXT", "MTEXT"}:
                texts += 1
            elif dxftype == "DIMENSION":
                dims += 1
            elif dxftype == "HATCH":
                hatches += 1
            elif dxftype in {"3DFACE", "MESH", "POLYFACE"}:
                has_3d = True

            # Check 3D thickness / elevation or non-zero Z coordinates
            if float(getattr(e.dxf, "thickness", 0.0) or 0.0) != 0.0:
                has_3d = True
            if float(getattr(e.dxf, "elevation", 0.0) or 0.0) != 0.0:
                has_3d = True

            # Sample bounds
            if dxftype == "LINE":
                all_pts.extend([[e.dxf.start.x, e.dxf.start.y], [e.dxf.end.x, e.dxf.end.y]])
                if abs(float(getattr(e.dxf.start, "z", 0.0))) > 1e-4 or abs(float(getattr(e.dxf.end, "z", 0.0))) > 1e-4:
                    has_3d = True
            elif dxftype == "LWPOLYLINE":
                pts = [[p[0], p[1]] for p in e.get_points("xy")]
                all_pts.extend(pts)

        report["texts_found"] = texts
        report["dimensions_found"] = dims
        report["hatches_found"] = hatches
        report["is_3d"] = has_3d

        if all_pts:
            report["extents"] = calculate_bounding_box(all_pts)
        else:
            # Fallback to header extents
            try:
                extmin = doc.header.get("$EXTMIN")
                extmax = doc.header.get("$EXTMAX")
                if extmin and extmax:
                    report["extents"] = {
                        "min_x": float(extmin[0]),
                        "min_y": float(extmin[1]),
                        "max_x": float(extmax[0]),
                        "max_y": float(extmax[1]),
                        "width": abs(float(extmax[0]) - float(extmin[0])),
                        "height": abs(float(extmax[1]) - float(extmin[1])),
                    }
            except Exception:
                pass

    except Exception as inspect_err:
        report["warnings"].append(f"Inspection notice: {inspect_err}")

    return report


def _units_from_header(document: Any) -> str:
    try:
        code = document.header.get("$INSUNITS", 0)
        return {1: "inch", 2: "feet", 4: "mm", 5: "cm", 6: "m"}.get(code, "drawing units")
    except Exception:
        return "drawing units"


def _repair_dxf_tags(dxf_text: str) -> str:
    lines = dxf_text.splitlines()
    repaired: list[str] = []
    i = 0
    in_lwpolyline = False
    has_subclass = False

    while i < len(lines):
        code = lines[i].strip()
        val = lines[i + 1].strip() if i + 1 < len(lines) else ""

        if code == "0":
            in_lwpolyline = (val == "LWPOLYLINE")
            has_subclass = False
            repaired.extend([code, val])
            i += 2
            continue

        if in_lwpolyline:
            if code == "100" and "AcDbPolyline" in val:
                has_subclass = True
            if code in {"90", "70", "10"} and not has_subclass:
                repaired.extend(["100", "AcDbEntity", "100", "AcDbPolyline"])
                has_subclass = True

        repaired.extend([code, val])
        i += 2

    return "\n".join(repaired) + "\n"


# =====================================================================
# 3. EXTRACTION OF ALL ENTITIES & METADATA (Sections 3 to 9, 29)
# =====================================================================

SUPPORTED_TYPES = {
    "LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE",
    "HATCH", "INSERT", "BLOCK", "TEXT", "MTEXT", "DIMENSION", "LEADER",
    "MLEADER", "3DFACE", "SOLID", "TRACE", "MESH", "POINT"
}


def read_drawing(path: Path) -> dict[str, Any]:
    """
    Parses EVERY entity from the DWG/DXF drawing, extracts all metadata, layers,
    blocks, texts, dimensions, hatches, and returns a fully structured drawing dict.
    Never silently discards an entity. Wrap each entity in try/except (Section 29).
    """
    validation_report = validate_and_inspect_drawing(path)

    dxf_path = convert_dwg_to_dxf(path) if path.suffix.lower() == ".dwg" else path
    cleanup_dxf = (dxf_path != path and dxf_path.parent.name == "output")

    try:
        doc = None
        recovery_note = ""
        try:
            doc = ezdxf.readfile(dxf_path)
        except Exception:
            try:
                raw_text = dxf_path.read_text(encoding="utf-8", errors="ignore")
                doc = ezdxf.read(io.StringIO(_repair_dxf_tags(raw_text)))
                recovery_note = "DXF tags sanitized successfully."
            except Exception:
                from ezdxf import recover
                try:
                    doc, auditor = recover.readfile(dxf_path)
                    if auditor.has_errors:
                        recovery_note = "Recovered with ezdxf recovery mode."
                except Exception as rec_err:
                    return _read_ascii_fallback(dxf_path, path.name, str(rec_err), validation_report)

        if doc is None:
            return _read_ascii_fallback(dxf_path, path.name, "Fallback triggered", validation_report)

        header_units = _units_from_header(doc)

        # -------------------------------------------------------------
        # Section 5: Layer Extraction Table
        # -------------------------------------------------------------
        layers_table: list[dict[str, Any]] = []
        layer_entity_counts: dict[str, int] = {}

        if hasattr(doc, "layers"):
            for layer in doc.layers:
                layer_name = layer.dxf.name
                layers_table.append({
                    "name": layer_name,
                    "color": getattr(layer.dxf, "color", 7),
                    "linetype": getattr(layer.dxf, "linetype", "Continuous"),
                    "visibility": not bool(layer.is_off()),
                    "frozen": bool(layer.is_frozen()),
                    "locked": bool(layer.is_locked()),
                    "entity_count": 0,
                })

        # -------------------------------------------------------------
        # Section 6: Block Definitions Table
        # -------------------------------------------------------------
        blocks_table: list[dict[str, Any]] = []
        if hasattr(doc, "blocks"):
            for blk in doc.blocks:
                blk_name = blk.name
                if not blk_name.startswith("*"):  # omit anonymous internal layouts
                    blocks_table.append({
                        "block_name": blk_name,
                        "description": getattr(blk, "description", ""),
                        "entities_count": len(list(blk)),
                    })

        # -------------------------------------------------------------
        # Section 3, 4, 29: Entity Extraction with Per-Entity Try/Except
        # -------------------------------------------------------------
        entities: list[dict[str, Any]] = []
        texts: list[dict[str, Any]] = []
        dimensions: list[dict[str, Any]] = []
        hatches: list[dict[str, Any]] = []
        blocks_instances: list[dict[str, Any]] = []
        parsing_warnings: list[dict[str, Any]] = []

        msp = doc.modelspace()
        counter = 1

        for entity in msp:
            dxftype = entity.dxftype()
            handle = getattr(entity.dxf, "handle", f"E{counter:04d}")
            layer = getattr(entity.dxf, "layer", "0")
            layer_entity_counts[layer] = layer_entity_counts.get(layer, 0) + 1

            try:
                rec = entity_record(entity, header_units)
                rec["handle"] = handle
                rec["id"] = f"E{counter:04d}"
                counter += 1

                # If entity is unsupported
                if dxftype not in SUPPORTED_TYPES:
                    rec["type"] = "UNKNOWN"
                    rec["handle"] = handle
                    rec["layer"] = layer
                    rec["raw_metadata"] = f"dxftype={dxftype}"

                entities.append(rec)

                # Section 6: Block INSERT Extraction
                if dxftype == "INSERT":
                    insert_rec = {
                        "block_name": rec.get("block_name"),
                        "position": rec.get("point", [0, 0]),
                        "rotation": rec.get("rotation", 0),
                        "scale": rec.get("scale", [1, 1, 1]),
                        "attributes": rec.get("attributes", {}),
                        "handle": handle,
                        "layer": layer,
                    }
                    blocks_instances.append(insert_rec)

                # Section 7: Text Extraction
                elif dxftype in {"TEXT", "MTEXT"}:
                    texts.append({
                        "id": rec["id"],
                        "handle": handle,
                        "type": dxftype,
                        "text": rec.get("text", ""),
                        "position": rec.get("point", [0, 0]),
                        "rotation": rec.get("rotation", 0),
                        "height": rec.get("height", 0),
                        "layer": layer,
                        "style": rec.get("style", "Standard"),
                    })

                # Section 8: Dimension Extraction
                elif dxftype == "DIMENSION":
                    dimensions.append({
                        "id": rec["id"],
                        "handle": handle,
                        "dimension_type": rec.get("dimension_type", 0),
                        "measured_value": rec.get("measurement"),
                        "defpoints": {
                            "defpoint": rec.get("defpoint"),
                            "defpoint2": rec.get("defpoint2"),
                            "defpoint3": rec.get("defpoint3"),
                        },
                        "text": rec.get("text", ""),
                        "layer": layer,
                    })

                # Section 9: Hatch Extraction
                elif dxftype == "HATCH":
                    hatches.append({
                        "id": rec["id"],
                        "handle": handle,
                        "pattern": rec.get("pattern_name", ""),
                        "scale": rec.get("pattern_scale", 1.0),
                        "angle": rec.get("pattern_angle", 0.0),
                        "area": rec.get("area", 0.0),
                        "layer": layer,
                    })

            except Exception as ent_err:
                # Section 29: Per-entity try/except
                err_rec = {
                    "type": "UNKNOWN",
                    "entity": dxftype,
                    "handle": handle,
                    "layer": layer,
                    "error": str(ent_err),
                }
                entities.append(err_rec)
                parsing_warnings.append(err_rec)

        # Update layer entity counts in table
        for l_entry in layers_table:
            l_entry["entity_count"] = layer_entity_counts.get(l_entry["name"], 0)

        # Detect true physical unit (mm vs m)
        detected_units, unit_scale = _detect_units_and_scale(header_units, entities)
        for e in entities:
            e["units"] = detected_units

        # Final structured drawing data
        parsed_drawing = {
            "file_name": path.name,
            "extension": path.suffix.lower(),
            "units": detected_units,
            "scale": "drawing units",
            "validation_report": validation_report,
            "layers": [l["name"] for l in layers_table] or sorted(list(layer_entity_counts.keys())),
            "layers_table": layers_table,
            "blocks_definitions": blocks_table,
            "blocks": blocks_instances,
            "texts": texts,
            "dimensions": dimensions,
            "hatches": hatches,
            "entities": entities,
            "counts": _counts(entities),
            "warnings": parsing_warnings,
            "notes": f"Extracted {len(entities)} entities. {recovery_note}".strip(),
        }

        # Lazy import of element_classifier to avoid circular dependency
        from backend.element_classifier import classify_construction_elements
        parsed_drawing["construction_elements"] = classify_construction_elements(parsed_drawing)

        return parsed_drawing

    finally:
        if cleanup_dxf and dxf_path.parent.exists():
            shutil.rmtree(dxf_path.parent.parent, ignore_errors=True)


def _detect_units_and_scale(header_units: str, entities: list[dict[str, Any]]) -> tuple[str, float]:
    lengths = [float(e.get("length", 0)) for e in entities if float(e.get("length", 0)) > 0]
    if not lengths:
        return ("mm", 0.001) if header_units in {"mm", "drawing units"} else (header_units, 1.0)

    lengths.sort()
    median_len = lengths[len(lengths) // 2]
    max_len = max(lengths)

    # Cross-validation: buildings are typically 3m-150m.
    # If coordinates are > 150 (e.g. 3000, 5000), drawing is in millimeters.
    if header_units == "m" and (median_len > 80 or max_len > 500):
        return "mm", 0.001
    elif header_units in {"mm", "cm", "m", "feet", "inch"}:
        scale = {"mm": 0.001, "cm": 0.01, "m": 1.0, "feet": 0.3048, "inch": 0.0254}[header_units]
        return header_units, scale

    if median_len > 80 or max_len > 500:
        return "mm", 0.001
    elif median_len > 0.5 and max_len < 100:
        return "m", 1.0
    elif 5 < median_len < 120:
        return "inch", 0.0254
    return "mm", 0.001


def _counts(entities: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {
        "total_entities": len(entities),
        "lines": sum(1 for e in entities if e.get("entity_type") == "LINE"),
        "polylines": sum(1 for e in entities if e.get("entity_type") in {"LWPOLYLINE", "POLYLINE"}),
        "circles": sum(1 for e in entities if e.get("entity_type") == "CIRCLE"),
        "arcs": sum(1 for e in entities if e.get("entity_type") == "ARC"),
        "hatches": sum(1 for e in entities if e.get("entity_type") == "HATCH"),
        "dimensions": sum(1 for e in entities if e.get("entity_type") == "DIMENSION"),
        "inserts": sum(1 for e in entities if e.get("entity_type") == "INSERT"),
        "texts": sum(1 for e in entities if e.get("entity_type") in {"TEXT", "MTEXT"}),
        "3dfaces": sum(1 for e in entities if e.get("entity_type") in {"3DFACE", "SOLID"}),
    }
    return counts


def _read_ascii_fallback(
    path: Path,
    file_name: str,
    error_msg: str,
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    """Robust ASCII tag parser for severely damaged DXF files."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    pairs: list[tuple[int, str]] = []
    i = 0
    while i < len(lines) - 1:
        c = lines[i].strip()
        v = lines[i + 1].strip()
        if c.isdigit() or (c.startswith("-") and c[1:].isdigit()):
            pairs.append((int(c), v))
            i += 2
        else:
            i += 1

    entities: list[dict[str, Any]] = []
    curr_kind = None
    curr_tags: list[tuple[int, str]] = []

    for code, val in pairs:
        if code == 0:
            if curr_kind and curr_kind not in {"SECTION", "ENDSEC", "EOF", "TABLE", "ENDTAB"}:
                rec = _parse_fallback_record(curr_kind, curr_tags)
                if rec:
                    entities.append(rec)
            curr_kind = val.strip()
            curr_tags = []
        else:
            curr_tags.append((code, val))

    if curr_kind and curr_kind not in {"SECTION", "ENDSEC", "EOF"}:
        rec = _parse_fallback_record(curr_kind, curr_tags)
        if rec:
            entities.append(rec)

    units, _ = _detect_units_and_scale("drawing units", entities)
    for e in entities:
        e["units"] = units

    parsed = {
        "file_name": file_name,
        "extension": ".dxf",
        "units": units,
        "scale": "drawing units",
        "validation_report": validation_report,
        "layers": sorted({x.get("layer", "0") for x in entities}),
        "layers_table": [],
        "blocks_definitions": [],
        "blocks": [e for e in entities if e.get("entity_type") == "INSERT"],
        "texts": [e for e in entities if e.get("entity_type") in {"TEXT", "MTEXT"}],
        "dimensions": [e for e in entities if e.get("entity_type") == "DIMENSION"],
        "hatches": [e for e in entities if e.get("entity_type") == "HATCH"],
        "entities": entities,
        "counts": _counts(entities),
        "warnings": [{"type": "FALLBACK", "message": error_msg}],
        "notes": f"ASCII tag recovery stream parser used ({error_msg}).",
    }

    from backend.element_classifier import classify_construction_elements
    parsed["construction_elements"] = classify_construction_elements(parsed)
    return parsed


def _parse_fallback_record(kind: str, tags: list[tuple[int, str]]) -> Optional[dict[str, Any]]:
    handle = next((v for c, v in tags if c == 5), None)
    layer = next((v for c, v in tags if c == 8), "0")
    record: dict[str, Any] = {
        "id": handle or "E000",
        "handle": handle,
        "entity_type": kind,
        "type": kind,
        "layer": layer,
        "points": [],
        "closed": False,
    }

    if kind == "LINE":
        xs = [float(v) for c, v in tags if c in (10, 11)]
        ys = [float(v) for c, v in tags if c in (20, 21)]
        if len(xs) >= 2 and len(ys) >= 2:
            p1, p2 = [xs[0], ys[0]], [xs[1], ys[1]]
            record["points"] = [p1, p2]
            record["length"] = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    elif kind in {"LWPOLYLINE", "POLYLINE"}:
        xs = [float(v) for c, v in tags if c == 10]
        ys = [float(v) for c, v in tags if c == 20]
        pts = [[x, y] for x, y in zip(xs, ys)]
        flags = int(next((v for c, v in tags if c == 70), 0) or 0)
        closed = bool(flags & 1)
        record["points"] = pts
        record["closed"] = closed
        if pts:
            perim = sum(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) for p1, p2 in zip(pts, pts[1:]))
            if closed and len(pts) > 2:
                perim += math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
            record["perimeter"] = perim
            record["length"] = perim
            record["area"] = _shoelace(pts) if (closed or len(pts) >= 3) else 0.0
    elif kind == "CIRCLE":
        cx = float(next((v for c, v in tags if c == 10), 0) or 0)
        cy = float(next((v for c, v in tags if c == 20), 0) or 0)
        r = float(next((v for c, v in tags if c == 40), 0) or 0)
        record.update({"center": [cx, cy], "radius": r, "area": math.pi * (r ** 2), "perimeter": 2 * math.pi * r, "length": 2 * math.pi * r})
    elif kind == "ARC":
        cx = float(next((v for c, v in tags if c == 10), 0) or 0)
        cy = float(next((v for c, v in tags if c == 20), 0) or 0)
        r = float(next((v for c, v in tags if c == 40), 0) or 0)
        sa = float(next((v for c, v in tags if c == 50), 0) or 0)
        ea = float(next((v for c, v in tags if c == 51), 360) or 360)
        sweep = math.radians((ea - sa) % 360)
        record.update({"center": [cx, cy], "radius": r, "length": abs(r * sweep)})
    elif kind == "INSERT":
        bx = float(next((v for c, v in tags if c == 10), 0) or 0)
        by = float(next((v for c, v in tags if c == 20), 0) or 0)
        block_name = next((v for c, v in tags if c == 2), None)
        record.update({"point": [bx, by], "block_name": block_name})
    elif kind in {"TEXT", "MTEXT"}:
        tx = float(next((v for c, v in tags if c == 10), 0) or 0)
        ty = float(next((v for c, v in tags if c == 20), 0) or 0)
        text = next((v for c, v in tags if c == 1), "")
        record.update({"point": [tx, ty], "text": text})
    elif kind == "HATCH":
        xs = [float(v) for c, v in tags if c == 10]
        ys = [float(v) for c, v in tags if c == 20]
        pts = [[x, y] for x, y in zip(xs, ys)]
        record["area"] = _shoelace(pts) if len(pts) >= 3 else 0.0
    elif kind == "DIMENSION":
        dim_text = next((v for c, v in tags if c == 1), "")
        meas = next((float(v) for c, v in tags if c == 42), None)
        record.update({"text": dim_text, "measurement": meas})

    pts = record.get("points", [])
    if pts:
        record["bbox"] = calculate_bounding_box(pts)

    return record
