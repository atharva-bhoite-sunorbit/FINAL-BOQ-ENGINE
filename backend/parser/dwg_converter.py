from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import winreg
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
BOQ_TEMP_DIR = REPO_ROOT / "backend" / "temp"
BOQ_TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(BOQ_TEMP_DIR)


def get_converter_path() -> Optional[Path]:
    # 1. Environment variable (supports .env configuration)
    env_path = os.environ.get("DWG_CONVERTER_PATH") or os.environ.get("BOQ_DWG_CONVERTER")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    # 2. Check repository bundled tools (LibreDWG)
    bundled = [
        REPO_ROOT / "tools libre" / "dwg2dxf.exe",
        REPO_ROOT / "tools libre" / "dwgread.exe",
        REPO_ROOT / "tools" / "LibreDWG" / "dwg2dxf.exe",
    ]
    for b in bundled:
        if b.exists():
            return b

    # 3. System PATH lookup
    for name in ("TeighaFileConverter", "ODAFileConverter", "dwg2dxf", "dwgread"):
        w = shutil.which(name)
        if w:
            return Path(w)

    # 4. Windows Registry / Program Files lookup for ODA
    oda_candidate = _find_oda_in_registry_or_program_files()
    if oda_candidate:
        return oda_candidate

    return None


def convert_dwg_to_dxf(input_path: Path) -> Path:
    if input_path.suffix.lower() == ".dxf":
        return input_path

    converter = get_converter_path()
    if not converter:
        raise RuntimeError(
            "DWG conversion tool not found. Configure DWG_CONVERTER_PATH in .env, "
            "install ODA File Converter, or upload a DXF file directly."
        )

    work_dir = Path(tempfile.mkdtemp(prefix="boq-dwg-", dir=BOQ_TEMP_DIR))
    input_dir = work_dir / "input"
    output_dir = work_dir / "output"
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    input_file = input_dir / input_path.name
    shutil.copy2(input_path, input_file)
    out_file = output_dir / f"{input_path.stem}.dxf"

    conv_name = converter.name.lower()

    if "dwg2dxf" in conv_name:
        cmd = [str(converter), "-y", "-o", str(out_file), str(input_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not out_file.exists() or out_file.stat().st_size == 0:
            # Fallback to dwgread.exe in same folder
            dwgread = converter.parent / "dwgread.exe"
            if dwgread.exists():
                cmd2 = [str(dwgread), "-O", "DXF", "-o", str(out_file), str(input_file)]
                res2 = subprocess.run(cmd2, capture_output=True, text=True, check=False)
                if res2.returncode != 0 and (not out_file.exists() or out_file.stat().st_size == 0):
                    raise RuntimeError(f"dwg2dxf and dwgread conversion failed: {result.stderr or res2.stderr}")
            else:
                raise RuntimeError(f"dwg2dxf failed: {result.stderr or result.stdout}")
    elif "dwgread" in conv_name:
        cmd = [str(converter), "-O", "DXF", "-o", str(out_file), str(input_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not out_file.exists():
            raise RuntimeError(f"dwgread failed: {result.stderr or result.stdout}")
    else:
        # Standard ODA File Converter CLI (input_dir, output_dir, version, type, recurse, audit)
        cmd = [str(converter), str(input_dir), str(output_dir), "ACAD2018", "DXF", "0", "1"]
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
            for cand in [
                Path(root) / "ODA" / "ODAFileConverter" / "ODAFileConverter.exe",
                Path(root) / "ODAFileConverter" / "ODAFileConverter.exe",
            ]:
                if cand.exists():
                    return cand
    return None
