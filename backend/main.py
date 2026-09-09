from pathlib import Path
from uuid import uuid4
import shutil
import json

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .services.dwg_reader import DWGReader
from .services.analysis_engine import analyze_dwg
from .services.material_engine import estimate_materials
from .services.boq_engine import build_boq
from .services.pdf_engine import build_pdf

BASE = Path(__file__).resolve().parents[1]
UPLOADS = BASE / "uploads"
REPORTS = BASE / "reports"
FRONTEND = BASE / "frontend"
UPLOADS.mkdir(exist_ok=True)
REPORTS.mkdir(exist_ok=True)

app = FastAPI(title="Construction BOQ Engine", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/app", StaticFiles(directory=str(FRONTEND)), name="app")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/health")
def health():
    reader = DWGReader()
    exe = reader.locate()
    return {
        "status": "ok",
        "dwg_reader": "ready" if exe else "missing",
        "dwg_reader_path": str(exe) if exe else None,
    }


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".dwg"):
        raise HTTPException(400, "Only .dwg files are accepted.")

    report_id = uuid4().hex
    dwg_path = UPLOADS / f"{report_id}.dwg"

    try:
        with dwg_path.open("wb") as target:
            shutil.copyfileobj(file.file, target)

        reader = DWGReader()
        if not reader.locate():
            raise HTTPException(
                500,
                "LibreDWG was not found. Expected tools\\LibreDWG\\dwgread.exe."
            )

        cad = reader.extract(dwg_path)
        analysis = analyze_dwg(cad)
        materials = estimate_materials(analysis)
        boq = build_boq(materials)

        # Persist a machine-readable audit report beside the PDF. This is useful
        # when a DWG produces unexpected parser results and lets us inspect the
        # exact entity/diagnostic information without rerunning the upload.
        json_path = REPORTS / f"{report_id}.json"
        json_path.write_text(
            json.dumps({
                "report_id": report_id,
                "filename": file.filename,
                "analysis": analysis,
                "materials": materials,
                "boq": boq,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        pdf_path = REPORTS / f"{report_id}.pdf"
        build_pdf(
            pdf_path,
            report_id,
            file.filename,
            analysis,
            materials,
            boq,
        )

        return {
            "report_id": report_id,
            "filename": file.filename,
            "analysis": analysis,
            "materials": materials,
            "boq": boq,
            "pdf_url": f"/api/report/{report_id}/pdf",
            "json_url": f"/api/report/{report_id}/json",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"DWG analysis failed: {exc}") from exc
    finally:
        await file.close()


@app.get("/api/report/{report_id}/json")
def report_json(report_id: str):
    path = REPORTS / f"{report_id}.json"
    if not path.exists():
        raise HTTPException(404, "Report not found.")
    return FileResponse(path, media_type="application/json", filename=f"BOQ_{report_id[:8]}.json")


@app.get("/api/report/{report_id}/pdf")
def pdf(report_id: str):
    path = REPORTS / f"{report_id}.pdf"
    if not path.exists():
        raise HTTPException(404, "Report not found.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"BOQ_{report_id[:8]}.pdf",
    )
