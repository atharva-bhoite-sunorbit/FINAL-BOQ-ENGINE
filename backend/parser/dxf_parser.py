from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Tuple
import ezdxf
from ezdxf import recover
from ezdxf.document import Drawing


def load_dxf_document(dxf_path: Path) -> Tuple[Drawing, str]:
    """
    Loads DXF document using ezdxf with automated tag sanitization for LibreDWG and recover mode.
    Returns the Drawing document and recovery notes.
    """
    recovery_note = ""
    try:
        doc = ezdxf.readfile(dxf_path)
        return doc, ""
    except Exception as exc:
        # 1. Try in-memory tag sanitization (adding missing 100 AcDbEntity / AcDbPolyline tags)
        try:
            raw_text = dxf_path.read_text(encoding="utf-8", errors="ignore")
            sanitized = sanitize_dxf_tags(raw_text)
            doc = ezdxf.read(io.StringIO(sanitized))
            return doc, "DXF tags sanitized and loaded successfully."
        except Exception:
            pass

        # 2. Try ezdxf recover mode
        try:
            doc, auditor = recover.readfile(dxf_path)
            note = "DXF recovery mode used." if auditor.has_errors else ""
            return doc, note
        except Exception as final_exc:
            raise RuntimeError(f"Unable to parse DXF structure: {exc}; Recover error: {final_exc}") from final_exc


def sanitize_dxf_tags(dxf_text: str) -> str:
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
