from __future__ import annotations

from typing import Any
from backend.models.cad_entity import CADEntity


class BlockParser:
    def __init__(self, doc=None):
        self.doc = doc

    def expand_block_inserts(self, doc, source_filename: str = "") -> list[CADEntity]:
        expanded: list[CADEntity] = []
        if not doc:
            return expanded

        insert_entities = [e for e in doc.modelspace() if e.dxftype() == "INSERT"]
        virtual_limit = 12000
        count = 0

        for ins in insert_entities:
            block_name = str(getattr(ins.dxf, "name", "") or "").upper()
            handle = getattr(ins.dxf, "handle", f"INS_{count}")

            # Expand blocks that define physical construction items
            should_expand = any(k in block_name for k in (
                "DOOR", "WINDOW", "COL", "BEAM", "COLUMN", "WALL", "SAN", "TOILET", "FURN", "LGT", "ELEC"
            ))

            if should_expand and hasattr(ins, "virtual_entities"):
                try:
                    for v in ins.virtual_entities():
                        if count >= virtual_limit:
                            break
                        v_type = v.dxftype()
                        v_handle = getattr(v.dxf, "handle", f"{handle}_V{count}")
                        v_layer = getattr(v.dxf, "layer", getattr(ins.dxf, "layer", "0"))

                        cad_e = CADEntity(
                            entity_id=f"VE{count:05d}",
                            entity_type=v_type,
                            layer=v_layer,
                            block_name=block_name,
                            handle=v_handle,
                            source_file=source_filename,
                            status="CLASSIFIED",
                        )
                        cad_e.extra_properties["source_insert_handle"] = handle

                        if v_type == "LINE":
                            p1 = [float(v.dxf.start.x), float(v.dxf.start.y)]
                            p2 = [float(v.dxf.end.x), float(v.dxf.end.y)]
                            cad_e.coordinates = [p1, p2]
                            cad_e.length = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
                            expanded.append(cad_e)
                            count += 1
                        elif v_type in {"LWPOLYLINE", "POLYLINE"}:
                            pts = [[float(p[0]), float(p[1])] for p in v.get_points("xy") if len(p) >= 2]
                            cad_e.coordinates = pts
                            expanded.append(cad_e)
                            count += 1
                except Exception:
                    pass

        return expanded
