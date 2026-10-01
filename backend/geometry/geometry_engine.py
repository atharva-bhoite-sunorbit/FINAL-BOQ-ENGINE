from __future__ import annotations

import logging
from typing import Any
from backend.models.construction_element import ConstructionElement

from .wall_detector import detect_walls
from .partition_detector import detect_partitions
from .column_detector import detect_columns
from .beam_detector import detect_beams
from .slab_detector import detect_slabs
from .foundation_detector import detect_foundations
from .footing_detector import detect_footings
from .pile_detector import detect_piles
from .pile_cap_detector import detect_pile_caps
from .shear_wall_detector import detect_shear_walls
from .retaining_wall_detector import detect_retaining_walls
from .lintel_detector import detect_lintels
from .staircase_detector import detect_staircases
from .ramp_detector import detect_ramps
from .door_detector import detect_doors
from .window_detector import detect_windows
from .opening_detector import detect_openings
from .glass_partition_detector import detect_glass_partitions
from .aluminium_partition_detector import detect_aluminium_partitions
from .drywall_detector import detect_drywalls
from .floor_detector import detect_floors
from .ceiling_detector import detect_ceilings
from .roof_detector import detect_roofs
from .parapet_detector import detect_parapets
from .railing_detector import detect_railings
from .handrail_detector import detect_handrails
from .cladding_detector import detect_claddings
from .room_detector import detect_rooms
from .grid_detector import detect_grids
from .axis_detector import detect_axes
from .electrical_detector import detect_electrical
from .plumbing_detector import detect_plumbing
from .sanitary_detector import detect_sanitary
from .hvac_detector import detect_hvac

logger = logging.getLogger(__name__)

ALL_DETECTORS = [
    # Structural
    ("FOUNDATION", detect_foundations),
    ("FOOTING", detect_footings),
    ("PILE", detect_piles),
    ("PILE_CAP", detect_pile_caps),
    ("COLUMN", detect_columns),
    ("BEAM", detect_beams),
    ("SLAB", detect_slabs),
    ("SHEAR_WALL", detect_shear_walls),
    ("RETAINING_WALL", detect_retaining_walls),
    ("LINTEL", detect_lintels),
    ("STAIRCASE", detect_staircases),
    ("RAMP", detect_ramps),
    # Masonry & Partitions
    ("WALL", detect_walls),
    ("PARTITION", detect_partitions),
    ("GLASS_PARTITION", detect_glass_partitions),
    ("ALUMINIUM_PARTITION", detect_aluminium_partitions),
    ("DRYWALL", detect_drywalls),
    # Openings
    ("DOOR", detect_doors),
    ("WINDOW", detect_windows),
    ("OPENING", detect_openings),
    # Finishes & Enclosures
    ("FLOOR", detect_floors),
    ("CEILING", detect_ceilings),
    ("ROOF", detect_roofs),
    ("PARAPET", detect_parapets),
    ("RAILING", detect_railings),
    ("HANDRAIL", detect_handrails),
    ("CLADDING", detect_claddings),
    ("ROOM", detect_rooms),
    # References
    ("GRID", detect_grids),
    ("AXIS", detect_axes),
    # MEP
    ("ELECTRICAL", detect_electrical),
    ("PLUMBING", detect_plumbing),
    ("SANITARY", detect_sanitary),
    ("HVAC", detect_hvac),
]


class GeometryEngine:
    def __init__(self) -> None:
        self.detectors = ALL_DETECTORS

    def detect_all(self, cad_data: dict[str, Any]) -> list[ConstructionElement]:
        all_elements: list[ConstructionElement] = []
        seen_handles: set[str] = set()

        for category, detector_fn in self.detectors:
            try:
                elements = detector_fn(cad_data)
                # Keep elements and track handles
                for elem in elements:
                    all_elements.append(elem)
                    for h in elem.source_entities:
                        seen_handles.add(h)
            except Exception as e:
                logger.error(f"Detector error in {category}: {e}")

        if not all_elements and cad_data.get("entities"):
            logger.info("No domain layer matches found. Running smart fallback geometric takeoff...")
            all_elements = self._detect_fallback_elements(cad_data)

        logger.info(f"GeometryEngine detected {len(all_elements)} construction elements.")
        return all_elements

    def _detect_fallback_elements(self, cad_data: dict[str, Any]) -> list[ConstructionElement]:
        """
        Guarantees that ANY drawing containing geometric entities (lines, polylines, hatches, circles)
        produces valid construction elements and a real BOQ even if layer names do not match known patterns.
        """
        fallback_elements: list[ConstructionElement] = []
        raw_ents = cad_data.get("entities", [])
        if not raw_ents:
            return fallback_elements

        default_height = 3.0
        default_thickness = 0.20

        for idx, entity in enumerate(raw_ents, start=1):
            if not isinstance(entity, dict):
                continue
            length = float(entity.get("length", 0.0) or 0.0)
            area = float(entity.get("area", 0.0) or 0.0)
            perimeter = float(entity.get("perimeter", 0.0) or 0.0)
            radius = float(entity.get("radius", 0.0) or 0.0)
            handle = entity.get("handle") or f"GEN_{idx}"
            layer = entity.get("layer", "0")

            # 1. Closed Areas (Slabs, Floors, Footings, Large Walls)
            if area > 0:
                if area >= 12.0:
                    thickness = 0.15
                    vol = area * thickness
                    elem = ConstructionElement(
                        element_id=f"FALLBACK_SLAB_{len(fallback_elements)+1:04d}",
                        element_type="SLAB",
                        subtype="RCC_SLAB",
                        geometry={"area": round(area, 4), "thickness": thickness, "volume": round(vol, 4), "perimeter": round(perimeter, 4)},
                        material_hint="CONCRETE",
                        source_entities=[str(handle)],
                        source_layers=[str(layer)],
                        confidence=0.75,
                        status="INFERRED",
                    )
                    fallback_elements.append(elem)
                elif 0.04 <= area < 2.5:
                    height = default_height
                    vol = area * height
                    elem = ConstructionElement(
                        element_id=f"FALLBACK_COL_{len(fallback_elements)+1:04d}",
                        element_type="COLUMN",
                        subtype="RCC_COLUMN",
                        geometry={"area": round(area, 4), "height": height, "volume": round(vol, 4), "perimeter": round(perimeter, 4)},
                        material_hint="CONCRETE",
                        source_entities=[str(handle)],
                        source_layers=[str(layer)],
                        confidence=0.75,
                        status="INFERRED",
                    )
                    fallback_elements.append(elem)
                else:
                    elem = ConstructionElement(
                        element_id=f"FALLBACK_FLR_{len(fallback_elements)+1:04d}",
                        element_type="FLOOR",
                        subtype="VITRIFIED_TILES",
                        geometry={"area": round(area, 4), "perimeter": round(perimeter, 4)},
                        material_hint="TILES",
                        source_entities=[str(handle)],
                        source_layers=[str(layer)],
                        confidence=0.70,
                        status="INFERRED",
                    )
                    fallback_elements.append(elem)

            # 2. Linear Elements (Walls, Partitions, Beams)
            elif length > 0:
                if length >= 1.5:
                    wall_vol = length * default_height * default_thickness
                    wall_area = length * default_height
                    elem = ConstructionElement(
                        element_id=f"FALLBACK_WALL_{len(fallback_elements)+1:04d}",
                        element_type="WALL",
                        subtype="BRICK_WALL",
                        geometry={
                            "length": round(length, 4),
                            "height": default_height,
                            "thickness": default_thickness,
                            "area": round(wall_area, 4),
                            "volume": round(wall_vol, 4),
                        },
                        material_hint="BRICK",
                        source_entities=[str(handle)],
                        source_layers=[str(layer)],
                        confidence=0.75,
                        status="INFERRED",
                    )
                    fallback_elements.append(elem)
                elif length >= 0.5:
                    part_thickness = 0.10
                    part_vol = length * default_height * part_thickness
                    part_area = length * default_height
                    elem = ConstructionElement(
                        element_id=f"FALLBACK_PART_{len(fallback_elements)+1:04d}",
                        element_type="PARTITION",
                        subtype="GYPSUM_PARTITION",
                        geometry={
                            "length": round(length, 4),
                            "height": default_height,
                            "thickness": part_thickness,
                            "area": round(part_area, 4),
                            "volume": round(part_vol, 4),
                        },
                        material_hint="GYPSUM",
                        source_entities=[str(handle)],
                        source_layers=[str(layer)],
                        confidence=0.70,
                        status="INFERRED",
                    )
                    fallback_elements.append(elem)

            # 3. Circular Elements
            elif radius > 0:
                col_area = 3.14159 * radius * radius
                vol = col_area * default_height
                elem = ConstructionElement(
                    element_id=f"FALLBACK_RCOL_{len(fallback_elements)+1:04d}",
                    element_type="COLUMN",
                    subtype="RCC_COLUMN",
                    geometry={"radius": round(radius, 4), "area": round(col_area, 4), "height": default_height, "volume": round(vol, 4)},
                    material_hint="CONCRETE",
                    source_entities=[str(handle)],
                    source_layers=[str(layer)],
                    confidence=0.75,
                    status="INFERRED",
                )
                fallback_elements.append(elem)

        return fallback_elements[:1000]


def detect_construction_elements(cad_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Legacy helper returning dictionary list for backward compatibility."""
    engine = GeometryEngine()
    elements = engine.detect_all(cad_data)
    return [el.to_dict() for el in elements]
