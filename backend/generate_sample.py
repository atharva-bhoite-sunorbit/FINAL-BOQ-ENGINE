from __future__ import annotations

import ezdxf

def generate_test_dxf(output_path: str):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # External Walls (230mm brick masonry)
    msp.add_lwpolyline([(0, 0), (12.5, 0), (12.5, 8.0), (0, 8.0)], close=True, dxfattribs={"layer": "I-WALL"})
    # Internal Partition Wall (75mm gypsum)
    msp.add_line((6.0, 0), (6.0, 8.0), dxfattribs={"layer": "I-WALL"})

    # Columns (300x450mm RCC)
    for pt in [(0, 0), (6.0, 0), (12.5, 0), (0, 8.0), (6.0, 8.0), (12.5, 8.0)]:
        msp.add_lwpolyline(
            [(pt[0], pt[1]), (pt[0] + 0.3, pt[1]), (pt[0] + 0.3, pt[1] + 0.45), (pt[0], pt[1] + 0.45)],
            close=True,
            dxfattribs={"layer": "STR-COL"}
        )

    # Doors (0.9m x 2.1m)
    msp.add_line((2.0, 0), (2.9, 0), dxfattribs={"layer": "A-DOOR"})
    msp.add_line((8.0, 0), (8.9, 0), dxfattribs={"layer": "A-DOOR"})

    # Windows (1.2m x 1.2m)
    msp.add_line((4.0, 8.0), (5.2, 8.0), dxfattribs={"layer": "A-WINDOW"})
    msp.add_line((9.0, 8.0), (10.2, 8.0), dxfattribs={"layer": "A-WINDOW"})

    # Flooring / Room boundary
    msp.add_lwpolyline([(0.3, 0.3), (5.7, 0.3), (5.7, 7.7), (0.3, 7.7)], close=True, dxfattribs={"layer": "A-FLOR"})

    # Annotations & Callouts
    msp.add_text("75MM GYPSUM PARTITION", dxfattribs={"layer": "I-WALL", "insert": (6.2, 4.0), "height": 0.25})
    msp.add_text("RCC M25 COLUMNS 8T16", dxfattribs={"layer": "STR-COL", "insert": (0.5, 0.5), "height": 0.25})
    msp.add_text("600X600 VITRIFIED TILES", dxfattribs={"layer": "A-FLOR", "insert": (2.0, 4.0), "height": 0.25})

    doc.saveas(output_path)
    print(f"Saved rich test DXF to {output_path}")

if __name__ == "__main__":
    generate_test_dxf("sample_project.dxf")
