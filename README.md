# Krisala Developers — Geometry-First BOQ Engine

A drawing-driven construction estimation engine with a FastAPI backend and a Krisala Developers workspace UI.

## Features
- Convert DWG to DXF through ODA/Teigha File Converter when configured
- Parse DXF LINE, POLYLINE, LWPOLYLINE, ARC, CIRCLE, HATCH, INSERT, TEXT, MTEXT and DIMENSION entities
- Preserve handles, layers, blocks, coordinates, measurements and parse errors
- Classify and group drawing geometry before applying configurable measurement rules
- Generate auditable quantities with source geometry and formulas
- Upload a manually prepared Excel/JSON BOQ and compare quantities through `/validate-boq`
- Download generated BOQ as PDF

## Run locally

```bash
cd D:\Sunorbit final BOQ
py -3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000
```

## DWG requirements

Native DWG conversion is deliberately not approximated. Install ODA File Converter or Teigha File Converter and expose `ODAFileConverter.exe` / `TeighaFileConverter.exe` on `PATH`, or configure an explicit executable:

```powershell
$env:BOQ_DWG_CONVERTER = 'C:\Path\To\ODAFileConverter.exe'
py -3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Alternatively, upload DXF directly.

The parser does not use a project filename or sample drawing. Every uploaded file goes through the same conversion, entity extraction, unit normalization, classification, grouping, quantity, material, and rate stages. Batch processing returns one document result per file and reports files that could not be processed without discarding successful results.

If the drawing has no measurable geometry or height/dimension evidence, the engine returns `NOT_DERIVABLE_FROM_DRAWING` instead of inventing quantities.

## API

- `POST /api/upload` — upload one DWG/DXF and generate an auditable BOQ
- `POST /api/upload-batch` — upload multiple DWG/DXF files; each file is parsed independently with the same geometry/classification/measurement pipeline
- `GET /api/boq/{doc_id}` — retrieve generated BOQ and calculation audit
- `POST /validate-boq` — compare an Excel/JSON reference BOQ against generated quantities
- `GET /api/validation/{doc_id}` — retrieve the latest validation result
- `GET /api/download-pdf/{doc_id}` — download PDF report
