# Construction BOQ Engine - Project 3

DWG-first construction quantity, material, BOQ and PDF workspace.

## Pipeline
DWG -> LibreDWG JSON + GeoJSON -> entity normalizer -> construction element detection -> geometry -> materials -> BOQ -> PDF

## Why two LibreDWG outputs?
LibreDWG JSON preserves DWG entity/type metadata while GeoJSON exposes ordinary geometry. The engine combines both instead of trusting a single export. This is important for complex DWGs containing INSERTs, LWPOLYLINEs, HATCHes, dimensions and proxy/custom objects.

## Run
1. Keep the complete Windows LibreDWG package in `tools\LibreDWG`.
2. Confirm `tools\LibreDWG\dwgread.exe --help` works.
3. Run `install.bat`.
4. Run `start.bat`.
5. Open `http://127.0.0.1:8000`.

## Analysis output
The dashboard now shows parser diagnostics for JSON, GeoJSON and DXF fallback. A machine-readable report is saved in `reports\<report_id>.json` beside the PDF.

## Accuracy
- Geometry-derived lengths/areas are preferred.
- Detected blocks/layers/text are used for semantic element identification.
- Height, thickness, reinforcement and material consumption are assumptions when the drawing does not provide those specifications.
- Rates are configurable planning rates and are not an approved project SOR.
- The engine must not be treated as a structural design or final procurement authority without engineer verification.

## Important
Do not add filename-specific rules for one test drawing. New DWGs should go through the same parser and normalizer.


## Material estimation upgrade (Project 3 v4)
This version expands the material takeoff to include:
- RMC/concrete by footings, columns, beams and slabs
- reinforcement steel by structural element
- binding wire
- masonry blocks, mortar, cement and sand
- doors and windows
- floor tiles, adhesive and grout
- plaster area, cement and sand
- primer, putty and paint
- waterproofing when a measurable waterproofing area is detected
- stair flights and estimated stair reinforcement
- planning BOQ rates and PDF/audit JSON

### Accuracy rule
The engine prioritizes geometry and schedule data from the DWG. If a required design value is not present, it uses a configurable estimating assumption and labels it. Reinforcement cannot be called exact from geometry alone; exact steel requires readable reinforcement schedules/details. RMC is treated as the procurement form of concrete. Cement/sand/aggregate equivalent quantities are reference-only when RMC is selected so the BOQ does not double count concrete procurement.
