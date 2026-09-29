from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

REPO_ROOT = Path(__file__).resolve().parents[1]
BOQ_TEMP_DIR = REPO_ROOT / "backend" / "temp"
BOQ_TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(BOQ_TEMP_DIR)
os.environ["TEMP"] = str(BOQ_TEMP_DIR)
os.environ["TMP"] = str(BOQ_TEMP_DIR)
