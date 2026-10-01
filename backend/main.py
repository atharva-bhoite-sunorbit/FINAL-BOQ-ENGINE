from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

# Prevent OpenBLAS memory allocation error on Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Header
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
from backend.construction_type_engine import ConstructionTypeEngine
from backend.labour_estimation_engine import LabourEstimationEngine

# Export
from backend.export import generate_boq_excel, generate_boq_pdf

# Legacy helpers for frontend compatibility
from backend.dwg_reader import converter_status, validate_and_inspect_drawing
from backend.boq_engine import generate_geometry_boq as legacy_generate_boq, generate_complete_boq
from backend.element_classifier import classify_entities as legacy_classify_entities
from backend.validation_engine import validate_boq as legacy_validate_boq

# Interactive Drawing Viewer & Engineering Analysis
from backend.drawing_analysis import (
    detect_units_with_confidence,
    detect_drawing_type,
    calculate_confidence_system,
    build_viewer_geometry,
)
from backend.revision_engine import compare_revisions
from backend.material_placement_engine import (
    get_material_placement_rules,
    run_material_placement_simulation,
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = REPO_ROOT / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
STORAGE_DIR = BOQ_TEMP_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Professional DWG/DXF Construction BOQ Engine",
    description="Deterministic CAD entity extraction, element detection, material systems takeoff, and audit-ready BOQ generation.",
    version="2.2.0",
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    code = "HTTP_ERROR"
    if exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 422:
        code = "DWG_PARSE_ERROR"
    elif exc.status_code == 400:
        code = "BAD_REQUEST"

    detail = exc.detail
    message = str(detail)
    if isinstance(detail, dict):
        message = detail.get("message", str(detail))
        code = detail.get("code", code)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": str(detail),
            },
            "detail": message,
        },
    )


@app.exception_handler(Exception)
async def custom_general_exception_handler(request: Request, exc: Exception):
    err_str = str(exc) or "Internal CAD processing error"
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "DWG_PARSE_ERROR",
                "message": f"Drawing Processing Failed: {err_str}",
                "details": err_str,
            },
            "detail": f"Drawing Processing Failed: {err_str}",
        },
    )

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/" or request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/", include_in_schema=False)
def serve_ui():
    resp = FileResponse(str(FRONTEND_DIR / "index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

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
    text_parser = TextParser(all_entities)
    specs = text_parser.extract_specifications()

    # 5. Dimension Parsing
    dim_parser = DimensionParser(all_entities)
    dims = dim_parser.extract_dimensions()

    # 6. Drawing View Detection
    view_parser = DrawingViewParser(all_entities)
    views = view_parser.detect_views()

    # 7. Unit Detection & Scale Calculation
    val_report = validate_and_inspect_drawing(dxf_path)
    units, unit_scale, unit_confidence, unit_verification_required = detect_units_with_confidence(
        doc, all_entities, specs, val_report
    )

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
    val_report["unit_confidence"] = unit_confidence
    val_report["unit_verification_required"] = unit_verification_required
    if isinstance(val_report.get("bounding_box"), dict) and unit_scale != 1.0:
        val_report["bounding_box"] = {k: v * unit_scale for k, v in val_report["bounding_box"].items()}

    # 8. Drawing Type Detection
    drawing_type_info = detect_drawing_type(all_entities, specs, layers, views)

    drawing_data = {
        "filename": original_filename,
        "units": units,
        "unit_scale": unit_scale,
        "unit_confidence": unit_confidence,
        "unit_verification_required": unit_verification_required,
        "drawing_type_detection": drawing_type_info,
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

    # Execute Construction Type Detection Engine
    cte = ConstructionTypeEngine()
    type_det = cte.detect_construction_type(drawing_data)
    drawing_data["construction_type_detection"] = type_det
    drawing_data["construction_type"] = type_det["construction_type"]
    drawing_data["construction_subtype"] = type_det["subtype"]
    drawing_data["construction_confidence"] = type_det["confidence"]
    drawing_data["confidence_level"] = type_det["confidence_level"]
    drawing_data["classification_source"] = type_det["classification_source"]
    drawing_data["classification_reason"] = type_det["classification_reason"]
    drawing_data["classification_timestamp"] = type_det["classification_timestamp"]
    drawing_data["classification_evidence"] = type_det["evidence"]

    # Execute BOQ Engine with construction type awareness
    boq_engine = BOQEngine()
    boq_res = boq_engine.generate_boq(
        drawing_data,
        construction_type=type_det["construction_type"],
        construction_subtype=type_det["subtype"],
    )
    drawing_data["boq_response"] = boq_res

    # Audit debug stats
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

    # Multi-signal confidence system calculation
    conf_system = calculate_confidence_system(
        file_valid=val_report.get("is_valid_cad", True),
        unit_confidence=unit_confidence,
        drawing_type_confidence=drawing_type_info.get("confidence", 0.85),
        elements=[el.to_dict() for el in elements],
        entities_count=len(all_entities),
        dims_count=len(dims),
        unclassified_count=unclassified_count,
    )
    drawing_data["confidence_breakdown"] = conf_system
    drawing_data["overall_verification_status"] = conf_system["overall_status"]

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
        "drawing_type": drawing_type_info,
        "confidence_breakdown": conf_system,
        "construction_type_detection": {
            "construction_type": type_det.get("construction_type"),
            "subtype": type_det.get("subtype"),
            "confidence": type_det.get("confidence"),
            "confidence_level": type_det.get("confidence_level"),
            "evidence": type_det.get("evidence", []),
            "source": type_det.get("classification_source"),
            "status": "AI Detected - Pending Verification" if type_det.get("classification_source") == "ai" else "Engineer Approved",
            "timestamp": type_det.get("classification_timestamp"),
        },
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
# PUBLIC V1 DEVELOPER API: DWG/DXF IN -> BOQ JSON OUT
# =====================================================================

def check_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """
    Validates optional API key.
    If BOQ_API_KEY environment variable is configured, requires matching X-API-Key header.
    If BOQ_API_KEY is not configured, allows requests in open developer mode.
    """
    configured_key = os.environ.get("BOQ_API_KEY", "").strip()
    if configured_key:
        if not x_api_key or x_api_key != configured_key:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized. A valid X-API-Key header is required to access this endpoint.",
            )
    return True


def format_api_v1_boq_response(
    record: dict[str, Any],
    include_materials: bool = True,
    include_labour: bool = True,
    include_elements: bool = False,
) -> dict[str, Any]:
    drawing_id = record.get("drawing_id") or record.get("id", "")
    boq_res = record.get("boq_response", {})
    raw_items = boq_res.get("boq", [])

    total_cost = sum(float(it.get("amount", 0.0) or 0.0) for it in raw_items)

    clean_items = []
    for it in raw_items:
        clean_items.append({
            "item_no": it.get("item_no") or it.get("sr_no"),
            "section": it.get("section", "GENERAL"),
            "element_type": it.get("element_type", "GEN"),
            "description": it.get("description", ""),
            "gross_quantity": it.get("gross_quantity", it.get("drawing_quantity", it.get("quantity", 0.0))),
            "opening_deduction": it.get("deduction_quantity", it.get("opening_deduction", 0.0)),
            "wastage_percent": it.get("wastage_percent", it.get("wastage_pct", 0.0)),
            "net_quantity": it.get("net_quantity", it.get("quantity", 0.0)),
            "final_quantity": it.get("total_quantity", it.get("final_quantity", 0.0)),
            "unit": it.get("unit", ""),
            "unit_rate": it.get("rate", it.get("final_rate", 0.0)),
            "amount": it.get("amount", 0.0),
            "calculation_basis": it.get("calculation_basis", it.get("calculation", "")),
            "status": it.get("status", "MEASURED"),
            "confidence": it.get("confidence", 0.95),
            "source_elements": it.get("source_elements") or it.get("source_element_ids") or [],
        })

    clean_materials = None
    if include_materials:
        clean_materials = []
        raw_mats = record.get("materials", [])
        for idx, m in enumerate(raw_mats, start=1):
            m_dict = dict(m) if isinstance(m, dict) else m.to_dict()
            clean_materials.append({
                "item_no": idx,
                "material": m_dict.get("material_name") or m_dict.get("material", "Material"),
                "category": m_dict.get("category", "Structural"),
                "base_quantity": m_dict.get("net_quantity", m_dict.get("quantity", 0.0)),
                "consumption_factor": m_dict.get("consumption_factor", 1.0),
                "final_quantity": m_dict.get("total_quantity", m_dict.get("final_quantity", 0.0)),
                "unit": m_dict.get("unit", ""),
                "unit_rate": m_dict.get("rate", m_dict.get("unit_rate", 0.0)),
                "total_cost": m_dict.get("amount", m_dict.get("total_cost", 0.0)),
                "calculation_basis": m_dict.get("calculation_basis", ""),
                "element_breakdown": m_dict.get("element_breakdown", {}),
            })

    c_type = record.get("construction_type") or "Residential"
    c_sub = record.get("construction_subtype") or "Apartment"

    labour_data = None
    if include_labour:
        labour_data = record.get("labour_timeline")
        if not labour_data:
            lee = LabourEstimationEngine()
            labour_data = lee.estimate_labour_and_timeline(raw_items, c_type, c_sub)
            record["labour_timeline"] = labour_data

    return {
        "success": True,
        "drawing_id": drawing_id,
        "filename": record.get("filename", "drawing.dwg"),
        "project_metadata": {
            "units": record.get("units", "m"),
            "unit_confidence": record.get("unit_confidence", 1.0),
            "drawing_type": record.get("drawing_type_detection", {}).get("type", "Plan"),
            "construction_type": c_type,
            "construction_subtype": c_sub,
            "classification_source": record.get("classification_source", "ai"),
            "confidence_level": record.get("confidence_level", "High"),
        },
        "summary": {
            "currency": "INR",
            "subtotal": round(total_cost, 2),
            "material_cost": round(total_cost * 0.70, 2),
            "labour_cost": round(total_cost * 0.30, 2),
            "tax": round(total_cost * 0.18, 2),
            "grand_total": round(total_cost * 1.18, 2),
            "boq_item_count": len(clean_items),
            "materials_count": len(clean_materials) if clean_materials is not None else len(record.get("materials", [])),
            "detected_elements_count": len(record.get("elements", [])),
        },
        "boq_items": clean_items,
        "materials_takeoff": clean_materials,
        "labour_timeline": labour_data,
        "detected_elements": record.get("elements") if include_elements else None,
    }


@app.post(
    "/api/v1/boq/generate-from-dwg",
    summary="Generate BOQ JSON from AutoCAD DWG or DXF Drawing",
    tags=["Public BOQ API"],
    response_description="Complete Construction BOQ Schedule and Material Takeoff in JSON format",
)
async def generate_boq_from_dwg_api(
    file: UploadFile = File(..., description="AutoCAD DWG (.dwg) or DXF (.dxf) drawing file"),
    rates: Optional[str] = Form(default=None, description="Optional JSON string of custom rate overrides"),
    construction_type: Optional[str] = Form(default=None, description="Optional construction type override (e.g. Residential, Commercial, Industrial)"),
    construction_subtype: Optional[str] = Form(default=None, description="Optional subtype override (e.g. Apartment, Villa, Office, Warehouse)"),
    include_materials: bool = Form(default=True, description="Whether to include detailed materials requirements schedule"),
    include_labour: bool = Form(default=True, description="Whether to include labour workforce and activity timeline"),
    include_elements: bool = Form(default=False, description="Whether to include raw detected structural CAD elements"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Public Developer API:
    - Input: Multipart upload of `.dwg` or `.dxf` drawing.
    - Output: Standardized Construction BOQ & Material Takeoff JSON.
    - Supports optional custom rate overrides and construction classification.
    """
    check_api_key(x_api_key)

    if not file.filename:
        raise HTTPException(status_code=400, detail="Drawing filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".dwg", ".dxf"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload an AutoCAD DWG (.dwg) or DXF (.dxf) file.",
        )

    drawing_id = str(uuid.uuid4())
    saved_path = UPLOAD_DIR / f"{drawing_id}_{file.filename}"
    with saved_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        record = parse_cad_drawing(saved_path, file.filename)
        record["drawing_id"] = drawing_id
    finally:
        saved_path.unlink(missing_ok=True)

    rate_overrides = None
    if rates:
        try:
            rate_overrides = json.loads(rates)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid rates JSON format: {exc}") from exc

    c_type = construction_type or record.get("construction_type") or "Residential"
    c_sub = construction_subtype or record.get("construction_subtype") or "Apartment"

    if construction_type:
        record["construction_type"] = c_type
        record["construction_subtype"] = c_sub
        record["classification_source"] = "api_user"

    # Re-run BOQ engine with overrides if provided
    if rate_overrides or construction_type:
        boq_engine = BOQEngine()
        boq_res = boq_engine.generate_boq(
            record,
            rate_overrides=rate_overrides,
            construction_type=c_type,
            construction_subtype=c_sub,
        )
        record["boq_response"] = boq_res

    save_drawing_record(drawing_id, record)

    return format_api_v1_boq_response(
        record,
        include_materials=include_materials,
        include_labour=include_labour,
        include_elements=include_elements,
    )


@app.get(
    "/api/v1/boq/{drawing_id}",
    summary="Retrieve computed BOQ JSON by Drawing ID",
    tags=["Public BOQ API"],
)
def get_boq_json_api(
    drawing_id: str,
    include_materials: bool = True,
    include_labour: bool = True,
    include_elements: bool = False,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Retrieves the structured BOQ JSON for a previously processed drawing ID.
    """
    check_api_key(x_api_key)
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")

    return format_api_v1_boq_response(
        record,
        include_materials=include_materials,
        include_labour=include_labour,
        include_elements=include_elements,
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
        src_el = it.get("source_elements") or it.get("source_element_ids") or []
        if isinstance(src_el, str):
            src_el = [s.strip() for s in src_el.split(",") if s.strip()]
        enr["source_elements"] = list(src_el)
        enr["source_element_ids"] = list(src_el)

        src_ent = it.get("source_entities", [])
        if isinstance(src_ent, str):
            src_ent = [s.strip() for s in src_ent.split(",") if s.strip()]
        enr["source_entities"] = list(src_ent)
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

        # Enhanced Material Requirements Schedule fields
        m_dict["material"] = m_dict.get("material_name") or m_dict.get("material") or "Material"
        m_dict["allowance"] = f"{m_dict.get('wastage_percent', 0)}%"
        m_dict["estimated_requirement"] = m_dict.get("final_quantity")
        m_dict["available_stock"] = 0.0
        m_dict["consumed"] = 0.0
        m_dict["remaining_requirement"] = m_dict.get("final_quantity")
        m_dict["procurement_gap"] = m_dict.get("final_quantity")
        m_dict["source"] = "CPWD / IS Standards"
        m_dict["confidence"] = f"{int(float(m_dict.get('confidence', 0.92)) * 100)}%"
        src_m_el = [s.strip() for s in str(m_dict.get("source_element_id") or "").split(",") if s.strip()]
        m_dict["source_element_ids"] = src_m_el
        m_dict["source_elements"] = src_m_el
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
                    existing.setdefault("source_element_ids", []).append(el)
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

            # Merge source element IDs
            for s_id in m.get("source_element_ids", []):
                if s_id and s_id not in existing.get("source_element_ids", []):
                    existing.setdefault("source_element_ids", []).append(s_id)
                    existing.setdefault("source_elements", []).append(s_id)

    for idx, m in enumerate(dedup_mats, start=1):
        m["sr_no"] = idx
    enriched_mats = dedup_mats

    total_cost = sum(float(it.get("amount", 0.0)) for it in enriched_items)

    # Calculate Labour Workforce & Construction Activities Timeline
    lee = LabourEstimationEngine()
    c_type = record.get("construction_type") or "Residential"
    c_sub = record.get("construction_subtype") or "Apartment"
    labour_timeline = lee.estimate_labour_and_timeline(enriched_items, c_type, c_sub)
    record["labour_timeline"] = labour_timeline

    # Build Interactive CAD Viewer Geometry
    viewer_geometry = build_viewer_geometry(
        record.get("entities", []),
        record.get("elements", []),
        enriched_items,
        record.get("units", "m"),
        drawing_name=file.filename or record.get("filename", ""),
    )
    record["viewer_geometry"] = viewer_geometry
    save_drawing_record(drawing_id, record)

    return {
        "success": True,
        "id": drawing_id,
        "filename": file.filename,
        "parsed": record,
        "labour_timeline": labour_timeline,
        "viewer_geometry": viewer_geometry,
        "construction_type": record.get("construction_type", "Residential"),
        "construction_subtype": record.get("construction_subtype", "Apartment"),
        "construction_confidence": record.get("construction_confidence", 0.90),
        "confidence_level": record.get("confidence_level", "High"),
        "classification_source": record.get("classification_source", "ai"),
        "classification_reason": record.get("classification_reason", ""),
        "classification_evidence": record.get("classification_evidence", []),
        "construction_type_detection": record.get("construction_type_detection", {}),
        "drawing_type_info": record.get("drawing_type_detection") or {},
        "confidence_breakdown": record.get("confidence_breakdown") or {},
        "overall_verification_status": record.get("overall_verification_status", "VERIFIED"),
        "unit_verification_required": record.get("unit_verification_required", False),
        "revisions": ["REV-01"],
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


# =====================================================================
# INTERACTIVE DRAWING VIEWER & BIDIRECTIONAL TRACEABILITY ENDPOINTS
# =====================================================================

@app.get("/api/drawings/{drawing_id}/geometry")
@app.get("/drawings/{drawing_id}/geometry")
def get_drawing_geometry(drawing_id: str):
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing not found")

    if "viewer_geometry" in record and record["viewer_geometry"]:
        return record["viewer_geometry"]

    geom = build_viewer_geometry(
        record.get("entities", []),
        record.get("elements", []),
        record.get("boq_response", {}).get("boq", []),
        record.get("units", "m"),
        drawing_name=record.get("filename", ""),
    )
    record["viewer_geometry"] = geom
    save_drawing_record(drawing_id, record)
    return geom


@app.get("/api/drawings/{drawing_id}/layers")
@app.get("/drawings/{drawing_id}/layers")
def get_drawing_layers(drawing_id: str):
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing not found")
    vg = record.get("viewer_geometry") or build_viewer_geometry(
        record.get("entities", []),
        record.get("elements", []),
        record.get("boq_response", {}).get("boq", []),
        record.get("units", "m"),
    )
    return {"drawing_id": drawing_id, "layers": vg.get("layers", [])}


@app.get("/api/drawings/{drawing_id}/elements")
@app.get("/drawings/{drawing_id}/elements")
def get_drawing_elements_endpoint(drawing_id: str):
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing not found")
    vg = record.get("viewer_geometry") or build_viewer_geometry(
        record.get("entities", []),
        record.get("elements", []),
        record.get("boq_response", {}).get("boq", []),
        record.get("units", "m"),
    )
    return {"drawing_id": drawing_id, "elements": vg.get("elements", [])}


@app.get("/api/drawings/{drawing_id}/elements/{element_id}")
@app.get("/drawings/{drawing_id}/elements/{element_id}")
def get_single_element_endpoint(drawing_id: str, element_id: str):
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing not found")
    vg = record.get("viewer_geometry") or build_viewer_geometry(
        record.get("entities", []),
        record.get("elements", []),
        record.get("boq_response", {}).get("boq", []),
        record.get("units", "m"),
    )
    for el in vg.get("elements", []):
        if el.get("element_id") == element_id:
            return el
    raise HTTPException(status_code=404, detail=f"Element {element_id} not found in drawing {drawing_id}")


@app.get("/api/drawings/{drawing_id}/elements/{element_id}/sources")
@app.get("/drawings/{drawing_id}/elements/{element_id}/sources")
def get_element_sources_endpoint(drawing_id: str, element_id: str):
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing not found")
    for el in record.get("elements", []):
        if el.get("element_id") == element_id:
            return {
                "element_id": element_id,
                "drawing_id": drawing_id,
                "source_entities": el.get("source_entities", []),
                "source_layers": el.get("source_layers", []),
                "source_dimensions": el.get("source_dimensions", []),
            }
    raise HTTPException(status_code=404, detail=f"Element {element_id} not found")


@app.get("/api/boq/{project_id}/items/{item_id}/sources")
@app.get("/boq/{project_id}/items/{item_id}/sources")
def get_boq_item_sources_endpoint(project_id: str, item_id: str):
    record = get_drawing_record(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Project/Drawing not found")
    items = record.get("boq_response", {}).get("boq", [])
    target = None
    for it in items:
        if str(it.get("item_no")) == str(item_id) or str(it.get("sr_no")) == str(item_id):
            target = it
            break
    if not target:
        raise HTTPException(status_code=404, detail=f"BOQ item {item_id} not found")

    return {
        "item_no": target.get("item_no"),
        "material": target.get("material"),
        "quantity": target.get("total_quantity"),
        "unit": target.get("unit"),
        "source_elements": target.get("source_elements") or target.get("source_element_ids") or [],
        "source_entities": target.get("source_entities", []),
        "source_layers": target.get("source_layers", []),
        "calculation_basis": target.get("calculation_basis", ""),
    }


@app.get("/api/boq/{project_id}/items/{item_id}/calculation")
@app.get("/boq/{project_id}/items/{item_id}/calculation")
def get_boq_item_calc_endpoint(project_id: str, item_id: str):
    record = get_drawing_record(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Project/Drawing not found")
    items = record.get("boq_response", {}).get("boq", [])
    target = None
    for it in items:
        if str(it.get("item_no")) == str(item_id) or str(it.get("sr_no")) == str(item_id):
            target = it
            break
    if not target:
        raise HTTPException(status_code=404, detail=f"BOQ item {item_id} not found")

    src_elements = target.get("source_elements") or target.get("source_element_ids") or []
    vg = record.get("viewer_geometry") or build_viewer_geometry(
        record.get("entities", []),
        record.get("elements", []),
        record.get("boq_response", {}).get("boq", []),
        record.get("units", "m"),
    )
    matched_elements = [el for el in vg.get("elements", []) if el.get("element_id") in src_elements]

    return {
        "item_no": target.get("item_no"),
        "material": target.get("material"),
        "gross_quantity": target.get("gross_quantity"),
        "deduction_quantity": target.get("deduction_quantity", 0.0),
        "wastage_percent": target.get("wastage_percent", 0.0),
        "total_quantity": target.get("total_quantity"),
        "unit": target.get("unit"),
        "calculation_basis": target.get("calculation_basis", ""),
        "formula": target.get("calculation") or target.get("calculation_basis") or "Gross Qty - Deductions",
        "deterministic": True,
        "contributing_elements_count": len(matched_elements),
        "elements": matched_elements,
    }


@app.get("/api/drawings/{drawing_id}/revisions")
@app.get("/drawings/{drawing_id}/revisions")
def get_revisions_endpoint(drawing_id: str):
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing not found")
    return {
        "drawing_id": drawing_id,
        "current_revision": "REV-01",
        "available_revisions": ["REV-01", "REV-02 (Simulated)", "REV-03 (Simulated)"],
    }


@app.get("/api/drawings/{drawing_id}/revisions/compare")
@app.get("/drawings/{drawing_id}/revisions/compare")
@app.post("/api/drawings/{drawing_id}/revisions/compare")
@app.post("/drawings/{drawing_id}/revisions/compare")
def compare_revisions_endpoint(
    drawing_id: str,
    rev1: Optional[str] = None,
    rev2: Optional[str] = None,
    rev_a: Optional[str] = None,
    rev_b: Optional[str] = None,
):
    r1 = rev_a or rev1 or "REV-01"
    r2 = rev_b or rev2 or "REV-02"
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing not found")
    base_elements = record.get("elements", [])
    base_boq = record.get("boq_response", {}).get("boq", [])

    revised_elements = [dict(e) for e in base_elements]
    if r2.startswith("REV-02") or r2.startswith("REV-03"):
        if revised_elements:
            revised_elements[0] = dict(revised_elements[0])
            g = dict(revised_elements[0].get("geometry", {}))
            g["length"] = round(float(g.get("length", 1.0)) + 1.2, 3)
            revised_elements[0]["geometry"] = g
            new_id = f"REV_ADD_{len(revised_elements)+1:04d}"
            revised_elements.append({
                "element_id": new_id,
                "element_type": "WALL",
                "subtype": "BRICK_WALL",
                "geometry": {"length": 4.5, "height": 3.0, "thickness": 0.23, "volume": 3.105},
                "confidence": 0.95,
                "status": "MEASURED",
            })

    diff_result = compare_revisions(base_elements, revised_elements, base_boq, base_boq)
    diff_result["counts"] = {
        "added": diff_result.get("summary", {}).get("added_count", 0),
        "removed": diff_result.get("summary", {}).get("removed_count", 0),
        "modified": diff_result.get("summary", {}).get("modified_count", 0),
    }
    return diff_result


@app.post("/api/drawings/{drawing_id}/measure")
@app.post("/drawings/{drawing_id}/measure")
async def measure_endpoint(
    drawing_id: str,
    request: Request,
):
    import json
    import math
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        pts = body.get("points", [])
        mode = body.get("mode", "distance")
    else:
        form = await request.form()
        raw_pts = form.get("points", "[]")
        mode = str(form.get("mode", "distance"))
        try:
            pts = json.loads(raw_pts) if isinstance(raw_pts, str) else raw_pts
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid points JSON")
    record = get_drawing_record(drawing_id)
    unit = record.get("units", "m") if record else "m"

    if mode == "distance" and len(pts) >= 2:
        dx = pts[1][0] - pts[0][0]
        dy = pts[1][1] - pts[0][1]
        dist = math.hypot(dx, dy)
        return {"mode": "distance", "value": round(dist, 3), "unit": unit, "formatted": f"{dist:.2f} {unit}"}
    elif mode == "area" and len(pts) >= 3:
        area = 0.0
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            area += pts[i][0] * pts[j][1]
            area -= pts[j][0] * pts[i][1]
        area = abs(area) / 2.0
        return {"mode": "area", "value": round(area, 3), "unit": f"{unit}²", "formatted": f"{area:.2f} {unit}²"}
    elif mode == "polyline" and len(pts) >= 2:
        total_len = 0.0
        for i in range(len(pts) - 1):
            total_len += math.hypot(pts[i+1][0] - pts[i][0], pts[i+1][1] - pts[i][1])
        return {"mode": "polyline", "value": round(total_len, 3), "unit": unit, "formatted": f"{total_len:.2f} {unit}"}

    return {"mode": mode, "value": 0.0, "unit": unit, "formatted": f"0.00 {unit}"}


@app.post("/api/drawing/{drawing_id}/unit")
async def update_drawing_unit(drawing_id: str, unit: str = Form(...)):
    """Allows user to override or confirm drawing unit and recalculates quantities."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing not found")
    valid_units = {"mm", "cm", "m", "in", "ft"}
    if unit.lower() not in valid_units:
        raise HTTPException(status_code=400, detail=f"Unit must be one of {valid_units}")

    unit_lower = unit.lower()
    scales = {"mm": 0.001, "cm": 0.01, "m": 1.0, "in": 0.0254, "ft": 0.3048}
    record["units"] = unit_lower
    record["unit_scale"] = scales.get(unit_lower, 1.0)
    record["unit_verification_required"] = False

    cb = record.get("confidence_breakdown") or {}
    cb["unit_detection"] = 100.0
    cb["unit_verification_required"] = False
    record["confidence_breakdown"] = cb

    boq_engine = BOQEngine()
    boq_res = boq_engine.generate_boq(record)
    record["boq_response"] = boq_res
    save_drawing_record(drawing_id, record)

    return {
        "status": "success",
        "drawing_id": drawing_id,
        "unit": unit_lower,
        "units": unit_lower,
        "unit_scale": record["unit_scale"],
        "boq_item_count": len(boq_res.get("boq", [])),
    }


# =====================================================================
# MATERIAL PLACEMENT SIMULATOR ENDPOINTS
# =====================================================================

@app.get("/api/simulator/rules")
def get_placement_rules_endpoint():
    """Returns configurable material placement simulation rules."""
    return get_material_placement_rules()


@app.post("/api/simulator/placement")
async def simulate_material_placement_endpoint(request: Request):
    """
    Simulates visual material placement directly on parsed CAD drawing geometry.
    Supports tiles, brick courses, concrete zones, paint/plaster surface coats, and plumbing pipes.
    """
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        drawing_id = body.get("drawing_id")
        material = body.get("material", "Floor Tiles")
        boq_item_id = body.get("boq_item_id")
        params = body.get("parameters", {})
    else:
        form = await request.form()
        drawing_id = form.get("drawing_id")
        material = form.get("material", "Floor Tiles")
        boq_item_id = form.get("boq_item_id")
        params_raw = form.get("parameters", "{}")
        import json
        try:
            params = json.loads(params_raw) if isinstance(params_raw, str) else params_raw
        except Exception:
            params = {}

    if not drawing_id:
        raise HTTPException(status_code=400, detail="drawing_id is required")

    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")

    placement_result = run_material_placement_simulation(
        drawing_record=record,
        material_name=material,
        boq_item_id=boq_item_id,
        user_parameters=params,
    )
    return placement_result


@app.get("/api/drawings/{drawing_id}/placement/{material_name}")
def get_drawing_material_placement(drawing_id: str, material_name: str, boq_item_id: Optional[str] = None):
    """Convenience GET endpoint for material placement simulation."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing not found")
    return run_material_placement_simulation(
        drawing_record=record,
        material_name=material_name,
        boq_item_id=boq_item_id,
        user_parameters=None,
    )


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


# =====================================================================
# AUTOMATIC CONSTRUCTION TYPE DETECTION ENDPOINTS
# =====================================================================

@app.post("/api/construction-type/detect")
async def detect_construction_type_endpoint(
    drawing_id: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    """
    Detects construction type from drawing_id or newly uploaded DWG/DXF file.
    """
    if drawing_id:
        record = get_drawing_record(drawing_id)
        if not record:
            raise HTTPException(status_code=404, detail="Drawing record not found")
        if "construction_type_detection" in record and record["construction_type_detection"]:
            return record["construction_type_detection"]
        cte = ConstructionTypeEngine()
        det = cte.detect_construction_type(record)
        record["construction_type_detection"] = det
        record["construction_type"] = det["construction_type"]
        record["construction_subtype"] = det["subtype"]
        record["construction_confidence"] = det["confidence"]
        record["confidence_level"] = det["confidence_level"]
        record["classification_source"] = det["classification_source"]
        record["classification_reason"] = det["classification_reason"]
        record["classification_timestamp"] = det["classification_timestamp"]
        record["classification_evidence"] = det["evidence"]
        save_drawing_record(drawing_id, record)
        return det

    if file:
        temp_id = str(uuid.uuid4())
        saved_path = UPLOAD_DIR / f"{temp_id}_{file.filename}"
        with saved_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        try:
            data = parse_cad_drawing(saved_path, file.filename)
            data["drawing_id"] = temp_id
            save_drawing_record(temp_id, data)
            return data.get("construction_type_detection", {})
        finally:
            saved_path.unlink(missing_ok=True)

    raise HTTPException(status_code=400, detail="Either drawing_id or file must be provided")


@app.post("/api/construction-type/confirm")
async def confirm_construction_type_endpoint(
    drawing_id: str = Form(...),
    construction_type: str = Form(...),
    construction_subtype: Optional[str] = Form(default=None),
    reason: Optional[str] = Form(default=None),
    rates: Optional[str] = Form(default=None),
):
    """
    Confirms or manually overrides the construction type (classification_source: engineer).
    Recalculates BOQ schedule and material rules accordingly.
    """
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    source = "engineer"

    record["construction_type"] = construction_type
    if construction_subtype:
        record["construction_subtype"] = construction_subtype
    record["classification_source"] = source
    record["classification_timestamp"] = now_iso
    if reason:
        record["classification_reason"] = reason

    det = record.get("construction_type_detection") or {}
    det["construction_type"] = construction_type
    if construction_subtype:
        det["subtype"] = construction_subtype
    det["classification_source"] = source
    det["classification_timestamp"] = now_iso
    det["status"] = "ENGINEER_APPROVED"
    record["construction_type_detection"] = det

    audit = record.get("audit_report") or {}
    audit["construction_type_detection"] = {
        "construction_type": construction_type,
        "subtype": record.get("construction_subtype"),
        "confidence": record.get("construction_confidence", 1.0),
        "confidence_level": record.get("confidence_level", "High"),
        "evidence": record.get("classification_evidence", []),
        "source": "Engineer Approved",
        "status": "Engineer Approved",
        "timestamp": now_iso,
    }
    record["audit_report"] = audit

    rate_overrides = None
    if rates:
        try:
            import json
            rate_overrides = json.loads(rates)
        except Exception:
            pass

    boq_engine = BOQEngine()
    boq_res = boq_engine.generate_boq(
        record,
        rate_overrides=rate_overrides,
        construction_type=construction_type,
        construction_subtype=record.get("construction_subtype"),
    )
    record["boq_response"] = boq_res

    lee = LabourEstimationEngine()
    labour_timeline = lee.estimate_labour_and_timeline(
        boq_res.get("boq", []),
        construction_type,
        record.get("construction_subtype") or "Standard"
    )
    record["labour_timeline"] = labour_timeline
    save_drawing_record(drawing_id, record)

    return {
        "status": "success",
        "drawing_id": drawing_id,
        "construction_type": construction_type,
        "subtype": record.get("construction_subtype"),
        "classification_source": source,
        "classification_timestamp": now_iso,
        "boq_item_count": len(boq_res.get("boq", [])),
    }


@app.get("/api/construction-type/{drawing_id}")
def get_construction_type_endpoint(drawing_id: str):
    """Retrieves current construction type detection and audit evidence for drawing."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")
    return {
        "drawing_id": drawing_id,
        "construction_type": record.get("construction_type"),
        "subtype": record.get("construction_subtype"),
        "confidence": record.get("construction_confidence"),
        "confidence_level": record.get("confidence_level"),
        "classification_source": record.get("classification_source"),
        "classification_reason": record.get("classification_reason"),
        "classification_timestamp": record.get("classification_timestamp"),
        "classification_evidence": record.get("classification_evidence", []),
        "detection": record.get("construction_type_detection", {}),
    }

@app.get("/api/labour-timeline/{drawing_id}")
def get_labour_timeline_endpoint(drawing_id: str):
    """Returns the construction timeline schedule and labour workforce takeoff."""
    record = get_drawing_record(drawing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Drawing record not found")
    if "labour_timeline" in record and record["labour_timeline"]:
        return record["labour_timeline"]
    lee = LabourEstimationEngine()
    c_type = record.get("construction_type") or "Residential"
    c_sub = record.get("construction_subtype") or "Apartment"
    items = record.get("boq_response", {}).get("boq", [])
    lt = lee.estimate_labour_and_timeline(items, c_type, c_sub)
    record["labour_timeline"] = lt
    save_drawing_record(drawing_id, record)
    return lt
