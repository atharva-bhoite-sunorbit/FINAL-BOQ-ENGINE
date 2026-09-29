from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

# Prevent OpenBLAS memory allocation error on Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Guarantee temp operations use backend/temp
REPO_ROOT = Path(__file__).resolve().parents[1]
BOQ_TEMP_DIR = REPO_ROOT / "backend" / "temp"
BOQ_TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(BOQ_TEMP_DIR)
os.environ["TEMP"] = str(BOQ_TEMP_DIR)
os.environ["TMP"] = str(BOQ_TEMP_DIR)

# Models
from backend.models.cad_entity import CADEntity
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity
from backend.models.boq_item import BOQItem

# Parser
from backend.parser.dwg_converter import convert_dwg_to_dxf, get_converter_path
from backend.parser.dxf_parser import load_dxf_document
from backend.parser.entity_extractor import extract_cad_entities
from backend.parser.layer_parser import LayerParser
from backend.parser.block_parser import BlockParser
from backend.parser.text_parser import TextParser
from backend.parser.dimension_parser import DimensionParser
from backend.parser.drawing_view_parser import DrawingViewParser

# Geometry
from backend.geometry.geometry_engine import GeometryEngine

# Materials
from backend.materials import MaterialEngine

# BOQ
from backend.boq import BOQEngine, BOQValidator

# Export
from backend.export import generate_boq_excel, generate_boq_pdf

# Legacy helpers for frontend compatibility
from backend.dwg_reader import converter_status, validate_and_inspect_drawing
from backend.boq_engine import generate_geometry_boq as legacy_generate_boq, generate_complete_boq
from backend.element_classifier import classify_entities as legacy_classify_entities
from backend.validation_engine import validate_boq as legacy_validate_boq

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = REPO_ROOT / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
STORAGE_DIR = BOQ_TEMP_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Professional DWG/DXF Construction BOQ Engine",
    description="Deterministic CAD entity extraction, element detection, material systems takeoff, and audit-ready BOQ generation.",
    version="2.1.0",
)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

# In-memory and persistent drawing storage
drawings_db: dict[str, dict[str, Any]] = {}


def save_drawing_record(drawing_id: str, record: dict[str, Any]):
    drawings_db[drawing_id] = record
    import json
    doc_file = STORAGE_DIR / f"{drawing_id}.json"
    try:
        doc_file.write_text(json.dumps(record, default=str), encoding="utf-8")
    except Exception:
        pass


def get_drawing_record(drawing_id: str) -> dict[str, Any] | None:
    if drawing_id in drawings_db:
        return drawings_db[drawing_id]
    import json
    doc_file = STORAGE_DIR / f"{drawing_id}.json"
    if doc_file.exists():
        try:
            data = json.loads(doc_file.read_text(encoding="utf-8"))
            drawings_db[drawing_id] = data
            return data
        except Exception:
            return None
    return None


def parse_cad_drawing(file_path: Path, original_filename: str) -> dict[str, Any]:
    """
    Parses a DWG or DXF file through the complete parser pipeline.
    """
    is_dwg = file_path.suffix.lower() == ".dwg"
    dxf_path = file_path

    if is_dwg:
        try:
            dxf_path = convert_dwg_to_dxf(file_path)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"DWG conversion failed: {exc}. Please verify DWG_CONVERTER_PATH or upload a DXF directly."
            ) from exc

    try:
        doc, recovery_note = load_dxf_document(dxf_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to load DXF file: {exc}") from exc

    # 1. Entity Extraction
    entities: list[CADEntity] = extract_cad_entities(doc, original_filename)

    # 2. Layer Analysis
    layer_parser = LayerParser()
    layers = [getattr(l.dxf, "name", "0") for l in doc.layers] if hasattr(doc, "layers") else []
    layer_analysis = [layer_parser.classify_layer(l) for l in layers]

    # 3. Block Expansion
    block_parser = BlockParser(doc)
    virtual_block_entities = block_parser.expand_block_inserts(doc, original_filename)
    all_entities = entities + virtual_block_entities

    # 4. Text and Annotation Analysis
    # Detect Units and calculate scale factor to standard SI meters
    units = "m"
    try:
        insunits = doc.header.get("$INSUNITS", 0)
        units_map = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}
        units = units_map.get(insunits, "m")
    except Exception:
        units = "m"

    val_report = validate_and_inspect_drawing(file_path)
    val_units = (val_report.get("units") or "").lower().strip()
    if val_units in {"mm", "cm", "m", "inch", "in", "feet", "ft"}:
        if units == "m" and val_units not in {"m", "drawing units"}:
            units = val_units

    unit_scale = 1.0
    u_lower = (units or "m").lower().strip()
    if u_lower in {"mm", "millimeter", "millimeters"}:
        unit_scale = 0.001
    elif u_lower in {"cm", "centimeter", "centimeters"}:
        unit_scale = 0.01
    elif u_lower in {"in", "inch", "inches"}:
        unit_scale = 0.0254
    elif u_lower in {"ft", "feet", "foot"}:
        unit_scale = 0.3048
    elif u_lower in {"m", "meter", "meters"}:
        unit_scale = 1.0
    else:
        # Heuristic check for unitless drawings ($INSUNITS=0):
        # In architectural drawings, if coordinate extents or wall lengths are > 100, units are mm
        max_extent = 0.0
        for e in all_entities:
            for p in e.coordinates:
                if len(p) >= 2:
                    max_extent = max(max_extent, abs(p[0]), abs(p[1]))
            if e.length > max_extent:
                max_extent = e.length
        if max_extent > 100.0:
            unit_scale = 0.001
            units = "mm"

    # Scale all CAD entities to standard meters so all volumetric and material math is physically real
    if unit_scale != 1.0:
        for e in all_entities:
            e.length = e.length * unit_scale
            e.area = e.area * (unit_scale ** 2)
            if e.coordinates:
                e.coordinates = [[p[0] * unit_scale, p[1] * unit_scale] if len(p) >= 2 else p for p in e.coordinates]
            if e.bounding_box:
                e.bounding_box = {k: v * unit_scale for k, v in e.bounding_box.items()}
            if "radius" in e.extra_properties:
                e.extra_properties["radius"] = float(e.extra_properties["radius"]) * unit_scale
            if e.dimension_value is not None and e.dimension_value > 0:
                e.dimension_value = e.dimension_value * unit_scale

    val_report["units"] = units
    val_report["unit_scale_to_meters"] = unit_scale
    if isinstance(val_report.get("bounding_box"), dict) and unit_scale != 1.0:
        val_report["bounding_box"] = {k: v * unit_scale for k, v in val_report["bounding_box"].items()}

    # 4. Text and Annotation Analysis
    text_parser = TextParser(all_entities)
    specs = text_parser.extract_specifications()

    # 5. Dimension Parsing
    dim_parser = DimensionParser(all_entities)
    dims = dim_parser.extract_dimensions()

    # 6. Drawing View Detection
    view_parser = DrawingViewParser(all_entities)
    views = view_parser.detect_views()

    drawing_data = {
        "filename": original_filename,
        "units": units,
        "unit_scale": unit_scale,
        "recovery_note": recovery_note,
        "validation_report": val_report,
        "entities": [e.to_dict() for e in all_entities],
        "layers": layers,
        "layer_analysis": layer_analysis,
        "texts": specs,
        "dimensions": dims,
        "drawing_views": views,
    }

    # Execute Geometry Engine
    geo_engine = GeometryEngine()
    elements: list[ConstructionElement] = geo_engine.detect_all(drawing_data)
    drawing_data["elements"] = [el.to_dict() for el in elements]

    # Execute Materials Engine
    mat_engine = MaterialEngine()
    materials: list[MaterialQuantity] = mat_engine.calculate_all(elements)
    drawing_data["materials"] = [m.to_dict() for m in materials]

    # Execute BOQ Engine
    boq_engine = BOQEngine()
    boq_res = boq_engine.generate_boq(drawing_data)
    drawing_data["boq_response"] = boq_res

    # Audit debug stats (Section 42)
    by_type: dict[str, int] = {}
    by_layer: dict[str, int] = {}
    unclassified_count = 0
    for e in all_entities:
        by_type[e.entity_type] = by_type.get(e.entity_type, 0) + 1
        by_layer[e.layer] = by_layer.get(e.layer, 0) + 1
        if e.status == "UNCLASSIFIED":
            unclassified_count += 1

    by_element: dict[str, int] = {}
    for el in elements:
        by_element[el.element_type] = by_element.get(el.element_type, 0) + 1

    drawing_data["audit_report"] = {
        "entity_count": len(all_entities),
        "layers": len(layers),
        "entities_by_type": by_type,
        "entities_by_layer": by_layer,
        "blocks": len([e for e in all_entities if e.entity_type == "INSERT"]),
        "dimensions": len(dims),
        "annotations": len(specs),
        "elements_detected": by_element,
        "walls": by_element.get("WALL", 0),
        "partitions": by_element.get("PARTITION", 0),
        "doors": by_element.get("DOOR", 0),
        "windows": by_element.get("WINDOW", 0),
        "columns": by_element.get("COLUMN", 0),
        "beams": by_element.get("BEAM", 0),
        "slabs": by_element.get("SLAB", 0),
        "unclassified": unclassified_count,
        "boq_item_count": len(boq_res.get("boq", [])),
    }

    return drawing_data


# =====================================================================
# SECTION 41 SPECIFIED ENDPOINTS
# =====================================================================

@app.post("/api/dwg/upload")
async def upload_dwg(file: UploadFile = File(...)):
    """Uploads DWG or DXF, converts if DWG, extracts entities, and returns summary."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".dwg", ".dxf"}:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a DWG or DXF file.")

    drawing_id = str(uuid.uuid4())
    saved_path = UPLOAD_DIR / f"{drawing_id}_{file.filename}"
    with saved_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        data = parse_cad_drawing(saved_path, file.filename)
        data["drawing_id"] = drawing_id
        save_drawing_record(drawing_id, data)
    finally:
        saved_path.unlink(missing_ok=True)

    return {
        "drawing_id": drawing_id,
        "filename": file.filename,
        "status": "PARSED_SUCCESSFULLY",
        "entity_count": len(data.get("entities", [])),
        "layer_count": len(data.get("layers", [])),
        "view_count": len(data.get("drawing_views", [])),
        "audit_report": data.get("audit_report", {}),
        "validation_report": data.get("validation_report", {}),
    }


@app.post("/api/dwg/parse")
async def parse_dwg_endpoint(file: UploadFile = File(...)):
    """Explicit endpoint for DWG parsing."""
    return await upload_dwg(file)


@app.post("/api/dxf/parse")
async def parse_dxf_endpoint(file: UploadFile = File(...)):
    """Direct DXF parsing endpoint (bypassing DWG conversion)."""
    return await upload_dwg(file)


@app.get("/api/drawing/{drawing_id}")
def get_drawing(drawing_id: str):
    """Returns the complete CAD entity extraction, layer analysis, and debug audit output."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")
    return {
        "drawing_id": drawing_id,
        "filename": record.get("filename"),
        "units": record.get("units"),
        "audit_report": record.get("audit_report"),
        "drawing_views": record.get("drawing_views"),
        "layers": record.get("layers"),
        "entities_sample": record.get("entities", [])[:100],
        "total_entities": len(record.get("entities", [])),
        "validation_report": record.get("validation_report", {}),
    }


@app.get("/api/validation-report/{drawing_id}")
def get_validation_report_endpoint(drawing_id: str):
    """Returns the Section 2 DWG/DXF structured validation report."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")
    return record.get("validation_report", {})


@app.get("/api/elements/{drawing_id}")
def get_elements(drawing_id: str):
    """Returns all detected construction elements with geometry and source CAD entities."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")
    return {
        "drawing_id": drawing_id,
        "element_count": len(record.get("elements", [])),
        "elements": record.get("elements", []),
    }


@app.get("/api/materials/{drawing_id}")
def get_materials(drawing_id: str):
    """Returns all mapped material quantities and multi-component systems."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")
    return {
        "drawing_id": drawing_id,
        "materials_count": len(record.get("materials", [])),
        "materials": record.get("materials", []),
    }


@app.post("/api/boq/generate")
async def generate_boq_endpoint(
    drawing_id: str = Form(...),
    rates: Optional[str] = Form(default=None),
):
    """Triggers or recalculates BOQ generation with optional rate overrides."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")

    rate_overrides = None
    if rates:
        import json
        try:
            rate_overrides = json.loads(rates)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid rates JSON: {exc}") from exc

    boq_engine = BOQEngine()
    boq_res = boq_engine.generate_boq(record, rate_overrides)
    record["boq_response"] = boq_res
    save_drawing_record(drawing_id, record)
    return boq_res


@app.get("/api/boq/{drawing_id}")
def get_boq(drawing_id: str):
    """Returns the Section 43 compliant final BOQ JSON payload."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")
    return record.get("boq_response", {})


@app.get("/api/boq/{drawing_id}/validation")
def get_boq_validation(drawing_id: str):
    """Returns the comprehensive 14-point validation audit result."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")
    boq_res = record.get("boq_response", {})
    return boq_res.get("validation", {"passed": True, "errors": [], "warnings": []})


@app.get("/api/boq/{drawing_id}/excel")
def download_excel_endpoint(drawing_id: str):
    """Streams the multi-tab styled openpyxl Excel spreadsheet."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")

    boq_res = record.get("boq_response", {})
    excel_bytes = generate_boq_excel(boq_res)
    clean_stem = Path(record.get("filename", "Project")).stem

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=BOQ_{clean_stem}_{drawing_id[:8]}.xlsx"},
    )


@app.get("/api/boq/{drawing_id}/pdf")
def download_pdf_endpoint(drawing_id: str):
    """Streams the landscape A4 ReportLab PDF report."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")

    boq_res = record.get("boq_response", {})
    pdf_bytes = generate_boq_pdf(boq_res)
    clean_stem = Path(record.get("filename", "Project")).stem

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=BOQ_{clean_stem}_{drawing_id[:8]}.pdf"},
    )


# =====================================================================
# FRONTEND / LEGACY COMPATIBILITY ENDPOINTS
# =====================================================================

@app.get("/")
def index():
    if (FRONTEND_DIR / "index.html").exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    return {"message": "Construction BOQ Engine API", "docs": "/docs"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "dwg_converter": converter_status(),
        "converter_path": str(get_converter_path()) if get_converter_path() else None,
    }


async def _process_single_upload(file: UploadFile, rates: Optional[str] = None) -> dict[str, Any]:
    res = await upload_dwg(file)
    drawing_id = res["drawing_id"]
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=500, detail="Failed to retrieve drawing record after upload")

    if rates:
        import json
        try:
            rate_overrides = json.loads(rates)
            boq_engine = BOQEngine()
            record["boq_response"] = boq_engine.generate_boq(record, rate_overrides)
            save_drawing_record(drawing_id, record)
        except Exception:
            pass

    boq_res = record["boq_response"]
    raw_items = boq_res.get("boq", [])
    total_cost = sum(float(it.get("amount", 0.0)) for it in raw_items)

    enriched_items = []
    for it in raw_items:
        enr = dict(it)
        enr["sr_no"] = it.get("item_no")
        enr["code"] = it.get("element_type", "GEN")
        enr["drawing_quantity"] = it.get("gross_quantity", it.get("quantity", 0))
        enr["opening_deduction"] = it.get("deduction_quantity", 0)
        enr["wastage_pct"] = it.get("wastage_percent", 0)
        enr["final_quantity"] = it.get("total_quantity")
        enr["final_rate"] = it.get("rate", 0)
        enr["calculation"] = it.get("calculation_basis", "")
        enr["status"] = it.get("status", "MEASURED")
        enr["confidence"] = it.get("confidence", 0.95)
        enr["source_elements"] = it.get("source_elements", [])
        enr["source_entities"] = it.get("source_entities", [])
        enr["section"] = it.get("section", "")
        enriched_items.append(enr)

    raw_mats = record.get("materials", [])
    enriched_mats = []
    for idx, m in enumerate(raw_mats, start=1):
        m_dict = dict(m)
        m_dict["sr_no"] = idx
        m_dict["derived_from"] = m.get("calculation_basis", m.get("derived_from", ""))
        m_dict["base_quantity"] = m.get("net_quantity", m.get("quantity", 0))
        m_dict["base_unit"] = m.get("unit", "")
        m_dict["consumption_factor"] = m.get("consumption_factor", 1.0)
        m_dict["final_quantity"] = m.get("total_quantity")
        m_dict["status"] = m.get("status", "MEASURED")
        m_dict["element_breakdown"] = m.get("element_breakdown", {})
        m_dict["unit_rate"] = m.get("rate", m.get("unit_rate", 0))
        m_dict["total_cost"] = m.get("amount", m.get("total_cost", 0))
        enriched_mats.append(m_dict)

    # Deduplicate BOQ items so each work item appears only once
    dedup_items = []
    seen_boq_keys = {}
    for it in enriched_items:
        desc_key = it.get("description", "")
        mat_key = it.get("material", "")
        unit_key = it.get("unit", "").strip().lower()
        sec_key = it.get("section", "").strip().upper()
        key = (sec_key, (mat_key or desc_key).strip().upper(), unit_key)

        if key not in seen_boq_keys:
            seen_boq_keys[key] = it
            dedup_items.append(it)
        else:
            existing = seen_boq_keys[key]
            q1 = existing.get("drawing_quantity") or 0.0
            q2 = it.get("drawing_quantity") or 0.0
            existing["drawing_quantity"] = round(q1 + q2, 4)

            d1 = existing.get("opening_deduction") or 0.0
            d2 = it.get("opening_deduction") or 0.0
            existing["opening_deduction"] = round(d1 + d2, 4)

            n1 = existing.get("net_quantity") or 0.0
            n2 = it.get("net_quantity") or 0.0
            existing["net_quantity"] = round(n1 + n2, 4)

            if existing.get("final_quantity") is not None and it.get("final_quantity") is not None:
                existing["final_quantity"] = round(existing["final_quantity"] + it["final_quantity"], 4)
                existing["amount"] = round(existing["final_quantity"] * existing.get("final_rate", 0.0), 2)
            elif existing.get("status") == "STRUCTURAL_REBAR_DATA_REQUIRED" or it.get("status") == "STRUCTURAL_REBAR_DATA_REQUIRED":
                existing["final_quantity"] = None
                existing["amount"] = 0.0
                existing["status"] = "STRUCTURAL_REBAR_DATA_REQUIRED"

            # Merge source elements & entities
            for el in it.get("source_elements", []):
                if el and el not in existing.get("source_elements", []):
                    existing.setdefault("source_elements", []).append(el)
            for ent in it.get("source_entities", []):
                if ent and ent not in existing.get("source_entities", []):
                    existing.setdefault("source_entities", []).append(ent)

    for idx, it in enumerate(dedup_items, start=1):
        it["sr_no"] = idx
        it["item_no"] = idx
    enriched_items = dedup_items

    # Deduplicate material items so each material appears only once
    dedup_mats = []
    seen_mat_keys = {}
    for m in enriched_mats:
        name_key = (m.get("material_name") or m.get("material") or "").strip().upper()
        unit_key = m.get("unit", "").strip().lower()
        key = (name_key, unit_key)

        if key not in seen_mat_keys:
            seen_mat_keys[key] = m
            dedup_mats.append(m)
        else:
            existing = seen_mat_keys[key]
            b1 = existing.get("base_quantity") or 0.0
            b2 = m.get("base_quantity") or 0.0
            existing["base_quantity"] = round(b1 + b2, 4)

            if existing.get("final_quantity") is not None and m.get("final_quantity") is not None:
                existing["final_quantity"] = round(existing["final_quantity"] + m["final_quantity"], 4)
                existing["total_cost"] = round(existing["final_quantity"] * existing.get("unit_rate", 0.0), 2)
            elif existing.get("status") == "STRUCTURAL_REBAR_DATA_REQUIRED" or m.get("status") == "STRUCTURAL_REBAR_DATA_REQUIRED":
                existing["final_quantity"] = None
                existing["total_cost"] = 0.0
                existing["status"] = "STRUCTURAL_REBAR_DATA_REQUIRED"

    for idx, m in enumerate(dedup_mats, start=1):
        m["sr_no"] = idx
    enriched_mats = dedup_mats

    total_cost = sum(float(it.get("amount", 0.0)) for it in enriched_items)
    return {
        "id": drawing_id,
        "filename": file.filename,
        "parsed": record,
        "validation_report": record.get("validation_report", {}),
        "elements": record.get("elements", []),
        "audit_report": record.get("audit_report", {}),
        "summary": {
            "item_count": len(enriched_items),
            "materials_count": len(enriched_mats),
            "subtotal": total_cost,
            "material_cost": round(total_cost * 0.70, 2),
            "labour_cost": round(total_cost * 0.30, 2),
            "tax": round(total_cost * 0.18, 2),
            "grand_total": round(total_cost * 1.18, 2),
        },
        "items": enriched_items,
        "materials": {"items": enriched_mats},
        "cost": {
            "subtotal": total_cost,
            "material_cost": round(total_cost * 0.70, 2),
            "labour_cost": round(total_cost * 0.30, 2),
            "tax": round(total_cost * 0.18, 2),
            "grand_total": round(total_cost * 1.18, 2),
        },
        "reports": {
            "raw_geometry": record.get("entities", [])[:100],
            "classification": record.get("audit_report", {}).get("elements_detected", {}),
            "quantity_takeoff": enriched_items,
            "material_takeoff": enriched_mats,
        },
    }


@app.post("/api/upload")
async def legacy_upload(file: UploadFile = File(...), rates: Optional[str] = Form(default=None)):
    """Legacy upload compatibility for existing frontend interface."""
    return await _process_single_upload(file, rates)


@app.post("/api/upload-batch")
async def legacy_upload_batch(files: list[UploadFile] = File(...), rates: Optional[str] = Form(default=None)):
    """Batch upload compatibility for multiple DWG/DXF drawings."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one drawing file is required")
    results = []
    errors = []
    for file in files:
        try:
            results.append(await _process_single_upload(file, rates))
        except HTTPException as exc:
            errors.append({"filename": file.filename, "error": exc.detail})
        except Exception as exc:
            errors.append({"filename": file.filename, "error": str(exc)})
    if not results:
        raise HTTPException(status_code=422, detail={"message": "No drawing could be processed", "errors": errors})
    return {"documents": results, "errors": errors}


def _read_reference_items(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        import json
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("items", payload) if isinstance(payload, dict) else payload
    try:
        from openpyxl import load_workbook
        workbook = load_workbook(path, read_only=True, data_only=True)
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="openpyxl is required for Excel validation") from exc
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="Reference workbook is empty")
    headers = [str(value or "").strip().lower() for value in rows[0]]
    aliases = {
        "item": ("item", "description", "material", "item code", "code"),
        "quantity": ("quantity", "qty", "final quantity"),
        "unit": ("unit", "uom"),
        "code": ("item code", "code"),
    }
    def index_for(names):
        return next((headers.index(name) for name in names if name in headers), None)
    item_index = index_for(aliases["item"])
    qty_index = index_for(aliases["quantity"])
    unit_index = index_for(aliases["unit"])
    code_index = index_for(aliases["code"])
    if item_index is None or qty_index is None:
        raise HTTPException(status_code=400, detail="Reference workbook needs item/description and quantity columns")
    return [
        {
            "item": row[item_index],
            "code": row[code_index] if code_index is not None else row[item_index],
            "quantity": float(row[qty_index] or 0),
            "unit": row[unit_index] if unit_index is not None else None,
        }
        for row in rows[1:] if row and row[item_index] is not None
    ]


@app.post("/validate-boq")
async def validate_uploaded_boq(
    reference: UploadFile = File(...),
    doc_id: str = Form(...),
    tolerance_percent: float = Form(default=1),
):
    doc = get_drawing_record(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="BOQ document not found")

    ref_path = UPLOAD_DIR / f"{uuid.uuid4()}_{reference.filename}"
    with ref_path.open("wb") as output:
        shutil.copyfileobj(reference.file, output)

    try:
        reference_items = _read_reference_items(ref_path)
        items = doc.get("boq_response", {}).get("boq", [])
        result = legacy_validate_boq(reference_items, items, tolerance_percent)
        doc["validation"] = result
        save_drawing_record(doc_id, doc)
        return result
    finally:
        ref_path.unlink(missing_ok=True)


@app.get("/api/download-excel/{doc_id}")
def legacy_excel(doc_id: str):
    return download_excel_endpoint(doc_id)


@app.get("/api/download-pdf/{doc_id}")
def legacy_pdf(doc_id: str):
    return download_pdf_endpoint(doc_id)


@app.get("/api/download-materials-excel/{doc_id}")
def legacy_mto(doc_id: str):
    return download_excel_endpoint(doc_id)
