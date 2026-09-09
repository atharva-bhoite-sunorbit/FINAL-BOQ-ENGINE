
RATES = {
    "AAC/Concrete Blocks": (75,"nos"), "Masonry Mortar": (3500,"m³"),
    "Cement - Masonry": (420,"bags"), "Sand - Masonry": (1800,"m³"),
    "Doors": (8500,"nos"), "Windows": (6500,"nos"),
    "RMC - Footing Concrete": (7500,"m³"), "RMC - Column Concrete": (7500,"m³"),
    "RMC - Beam Concrete": (7500,"m³"), "RMC - Slab Concrete": (7500,"m³"),
    "Cement Equivalent - Footing Concrete": (420,"bags"), "Cement Equivalent - Column Concrete": (420,"bags"),
    "Cement Equivalent - Beam Concrete": (420,"bags"), "Cement Equivalent - Slab Concrete": (420,"bags"),
    "Sand Equivalent - Footing Concrete": (1800,"m³"), "Sand Equivalent - Column Concrete": (1800,"m³"),
    "Sand Equivalent - Beam Concrete": (1800,"m³"), "Sand Equivalent - Slab Concrete": (1800,"m³"),
    "Aggregate Equivalent - Footing Concrete": (1600,"m³"), "Aggregate Equivalent - Column Concrete": (1600,"m³"),
    "Aggregate Equivalent - Beam Concrete": (1600,"m³"), "Aggregate Equivalent - Slab Concrete": (1600,"m³"),
    "Reinforcement Steel - Footings": (72,"kg"), "Reinforcement Steel - Columns": (72,"kg"),
    "Reinforcement Steel - Beams": (72,"kg"), "Reinforcement Steel - Slabs": (72,"kg"),
    "Reinforcement Steel - Stairs": (72,"kg"),
    "Binding Wire - Footings": (90,"kg"), "Binding Wire - Columns": (90,"kg"),
    "Binding Wire - Beams": (90,"kg"), "Binding Wire - Slabs": (90,"kg"),
    "Floor Tiles": (1200,"m²"), "Tile Adhesive": (55,"kg"), "Tile Grout": (120,"kg"),
    "Stair Flights": (5000,"nos"), "Plaster Area": (220,"m²"),
    "Cement - Plaster": (420,"bags"), "Sand - Plaster": (1800,"m³"),
    "Primer": (180,"L"), "Wall Putty": (55,"kg"), "Paint": (250,"L"),
    "Waterproofing": (300,"m²"), "Waterproofing Material": (180,"kg"),
}

def build_boq(materials):
    rows=[]
    for i,m in enumerate(materials.get("items",[]),1):
        q=float(m.get("quantity",0)); name=m["material"]
        rate,unit=RATES.get(name,(0,m.get("unit","")))
        commercial=bool(m.get("commercial",True)) and not name.startswith(("Cement Equivalent -","Sand Equivalent -","Aggregate Equivalent -"))
        rows.append({"sr_no":i,"description":name,"quantity":round(q,3),"unit":m.get("unit") or unit,
                     "rate":rate if commercial else 0,"amount":round(q*rate,2) if commercial else 0,
                     "status":("REFERENCE ONLY" if not commercial else m.get("source","REVIEW")),
                     "basis":m.get("basis",""),"category":m.get("category","Material")})
    total=round(sum(r["amount"] for r in rows),2)
    return {"items":rows,"subtotal":total,"grand_total":total,"currency":"INR",
            "rate_note":"Planning rates only. Replace with approved project SOR/vendor rates before commercial use.",
            "rcc_note":"RMC is procurement quantity. Site-mix equivalent cement/sand/aggregate lines are informational and should not be added to RMC concrete cost simultaneously."}
