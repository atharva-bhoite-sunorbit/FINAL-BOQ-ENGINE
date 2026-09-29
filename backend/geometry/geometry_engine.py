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

        logger.info(f"GeometryEngine detected {len(all_elements)} construction elements.")
        return all_elements


def detect_construction_elements(cad_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Legacy helper returning dictionary list for backward compatibility."""
    engine = GeometryEngine()
    elements = engine.detect_all(cad_data)
    return [el.to_dict() for el in elements]
