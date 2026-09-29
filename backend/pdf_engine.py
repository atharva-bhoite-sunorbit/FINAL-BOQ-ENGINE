from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

# Ensure temp files use Drive D
REPO_ROOT = Path(__file__).resolve().parents[1]
BOQ_TEMP_DIR = REPO_ROOT / "backend" / "temp"
BOQ_TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(BOQ_TEMP_DIR)
os.environ["TEMP"] = str(BOQ_TEMP_DIR)
os.environ["TMP"] = str(BOQ_TEMP_DIR)

from backend.export.pdf_engine import generate_boq_pdf as _export_pdf


def generate_boq_pdf(boq_data: dict[str, Any]) -> bytes:
    """
    Section 30 Architecture: pdf_engine.py
    Generates production-grade landscape A4 ReportLab PDF report.
    """
    return _export_pdf(boq_data)
