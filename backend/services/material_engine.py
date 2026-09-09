
import re
from collections import defaultdict

# All values are configurable estimating rules. Drawing/schedule-derived values take priority.
RULES = {
    "default_wall_height_m": 3.0,
    "default_wall_thickness_m": 0.23,
    "block_length_m": 0.60, "block_height_m": 0.20, "block_thickness_m": 0.20,
    "mortar_fraction": 0.20,
    "cement_bags_per_m3_mortar": 8.0, "sand_m3_per_m3_mortar": 1.20,
    "slab_thickness_m": 0.125,
    "beam_width_m": 0.23, "beam_depth_m": 0.45,
    "column_width_m": 0.30, "column_depth_m": 0.30, "column_height_m": 3.0,
    "footing_x_m": 1.50, "footing_y_m": 1.50, "footing_depth_m": 0.30,
    "stair_rise_m": 0.16, "stair_tread_m": 0.28, "stair_width_m": 1.20,
    "rcc_cement_bags_per_m3": 8.0, "rcc_sand_m3_per_m3": 0.42,
    "rcc_aggregate_m3_per_m3": 0.84,
    "steel_kg_per_m3": {"footings":80,"columns":150,"beams":160,"slabs":100,"stairs":110},
    "tile_wastage":0.05, "tile_adhesive_kg_per_m2":4.0, "tile_grout_kg_per_m2":0.25,
    "plaster_thickness_m":0.012, "plaster_cement_bags_per_m3":7.0,
    "plaster_sand_m3_per_m3":1.20, "paint_litres_per_m2":0.18,
    "primer_litres_per_m2":0.10, "putty_kg_per_m2":1.0,
    "waterproofing_kg_per_m2":1.5, "binding_wire_kg_per_tonne_steel":10.0,
    "excavation_factor":1.20
}

def item(material,qty,unit,basis,source,category="Material",commercial=True):
    return {"material":material,"quantity":round(max(0,float(qty or 0)),3),"unit":unit,
            "basis":basis,"source":source,"category":category,"commercial":commercial}

def _element(elements,name):
    return next((x for x in elements if x.get("name")==name),None)

def _dims(e):
    vals=e.get("dimension_hints") or []
    for a,b in vals:
        # CAD structural dimensions are often mm; convert if plausible.
        a,b=float(a),float(b)
        if max(a,b)>20: a,b=a/1000,b/1000
        yield a,b

def _section(e,default_w,default_d):
    for a,b in _dims(e):
        if 0.08<=a<=2 and 0.08<=b<=2:return min(a,b),max(a,b),"DRAWING-DERIVED"
    return default_w,default_d,"ASSUMPTION"

def _append_rcc_breakdown(out,label,vol,source):
    if vol<=0:return
    out.append(item(f"RMC - {label}",vol,"m³",f"{label} concrete volume",source,"RCC"))
    # Site-mix equivalent is informational; not added to total when RMC is selected.
    out.append(item(f"Cement Equivalent - {label}",vol*RULES["rcc_cement_bags_per_m3"],"bags",
                    f"RMC volume × cement coefficient (site-mix equivalent)", "DERIVED+ASSUMPTION","RCC"))
    out.append(item(f"Sand Equivalent - {label}",vol*RULES["rcc_sand_m3_per_m3"],"m³",
                    "RMC volume × sand coefficient (site-mix equivalent)", "DERIVED+ASSUMPTION","RCC",False))
    out.append(item(f"Aggregate Equivalent - {label}",vol*RULES["rcc_aggregate_m3_per_m3"],"m³",
                    "RMC volume × aggregate coefficient (site-mix equivalent)", "DERIVED+ASSUMPTION","RCC",False))

def estimate_materials(analysis):
    es=analysis.get("elements",[]);out=[];warnings=[]

    wall=_element(es,"Walls")
    if wall:
        length=wall.get("length_m",0); area=wall.get("area_m2",0)
        thickness=RULES["default_wall_thickness_m"]; height=RULES["default_wall_height_m"]; source="ASSUMPTION"
        w,h,_=_section(wall,thickness,0.0)
        if w>0: thickness=w
        if length>0:
            volume=length*height*thickness; basis=f"Wall length {length:.3f} m × height {height:.3f} m × thickness {thickness:.3f} m"
        elif area>0:
            volume=area*thickness; basis=f"Wall area {area:.3f} m² × thickness {thickness:.3f} m"
        else: volume=0;basis="Insufficient wall geometry"
        if volume:
            if wall.get("dimension_hints"):source="DRAWING-DERIVED+ASSUMPTION"
            block_vol=RULES["block_length_m"]*RULES["block_height_m"]*RULES["block_thickness_m"]
            gross_blocks=volume/block_vol
            openings=sum(_element(es,n).get("count",0) for n in ("Doors","Windows") if _element(es,n))
            # Opening deduction is only a conservative allowance because exact opening sizes may be unavailable.
            deduction=min(0.30,max(0,openings*0.02))
            net_vol=volume*(1-deduction)
            out += [item("AAC/Concrete Blocks",net_vol/block_vol,"nos",f"Net masonry volume {net_vol:.3f} m³; opening allowance {deduction*100:.1f}%","DERIVED+ASSUMPTION","Masonry"),
                    item("Masonry Mortar",net_vol*RULES["mortar_fraction"],"m³","Net wall volume × mortar fraction","DERIVED+ASSUMPTION","Masonry"),
                    item("Cement - Masonry",net_vol*RULES["mortar_fraction"]*RULES["cement_bags_per_m3_mortar"],"bags","Mortar volume × cement consumption","DERIVED+ASSUMPTION","Masonry"),
                    item("Sand - Masonry",net_vol*RULES["mortar_fraction"]*RULES["sand_m3_per_m3_mortar"],"m³","Mortar volume × sand consumption","DERIVED+ASSUMPTION","Masonry")]

    # openings
    for n in ("Doors","Windows"):
        e=_element(es,n)
        if e:
            out.append(item(n,e["count"],"nos","Detected blocks/entities", "DRAWING-DETECTED", "Openings"))

    # structural elements with actual length/area where possible
    structural=[("Footings","Footing"),("Columns","Column"),("Beams","Beam")]
    for en,label in structural:
        e=_element(es,en)
        if not e:continue
        if en=="Beams":
            w,d,src=_section(e,RULES["beam_width_m"],RULES["beam_depth_m"])
            vol=e.get("length_m",0)*w*d
        elif en=="Columns":
            w,d,src=_section(e,RULES["column_width_m"],RULES["column_depth_m"])
            vol=e.get("count",0)*w*d*RULES["column_height_m"]
        else:
            w,d,src=_section(e,RULES["footing_x_m"],RULES["footing_y_m"])
            depth=RULES["footing_depth_m"]
            vol=e.get("count",0)*w*d*depth
        if vol:
            _append_rcc_breakdown(out,label+" Concrete",vol,"DRAWING-DERIVED" if (e.get("length_m",0)>0 and en=="Beams") else ("DRAWING-DERIVED+ASSUMPTION" if e.get("dimension_hints") else "ASSUMPTION"))
            steel_rate=RULES["steel_kg_per_m3"][en.lower()]
            steel=vol*steel_rate
            steel_source="ASSUMPTION"
            out.append(item(f"Reinforcement Steel - {label}s",steel,"kg",f"{label} concrete volume × reinforcement coefficient {steel_rate} kg/m³",steel_source,"Reinforcement"))
            out.append(item(f"Binding Wire - {label}s",steel/1000*RULES["binding_wire_kg_per_tonne_steel"],"kg","Steel tonnage × binding wire coefficient","DERIVED+ASSUMPTION","Reinforcement"))

    slab=_element(es,"Slabs")
    if slab:
        area=slab.get("area_m2",0)
        if area:
            vol=area*RULES["slab_thickness_m"]
            _append_rcc_breakdown(out,"Slab Concrete",vol,"DRAWING-DERIVED+ASSUMPTION")
            steel=vol*RULES["steel_kg_per_m3"]["slabs"]
            out.append(item("Reinforcement Steel - Slabs",steel,"kg","Slab concrete × slab steel coefficient","ASSUMPTION","Reinforcement"))

    flooring=_element(es,"Flooring")
    if flooring and flooring.get("area_m2",0)>0:
        a=flooring["area_m2"]*(1+RULES["tile_wastage"])
        out += [item("Floor Tiles",a,"m²",f"Flooring area {flooring['area_m2']:.3f} m² + 5% wastage","DERIVED","Finishes"),
                item("Tile Adhesive",a*RULES["tile_adhesive_kg_per_m2"],"kg","Tile area × adhesive consumption","DERIVED+ASSUMPTION","Finishes"),
                item("Tile Grout",a*RULES["tile_grout_kg_per_m2"],"kg","Tile area × grout consumption","DERIVED+ASSUMPTION","Finishes")]

    stairs=_element(es,"Stairs")
    if stairs and stairs.get("count",0)>0:
        # A stair flight cannot be dimensioned exactly from a count alone.
        steel=stairs["count"]*RULES["stair_width_m"]*2.0*RULES["steel_kg_per_m3"]["stairs"]
        out.append(item("Stair Flights",stairs["count"],"nos","Detected stair entities","DRAWING-DETECTED","Stairs"))
        out.append(item("Reinforcement Steel - Stairs",steel,"kg","Configured flight geometry/steel allowance","ASSUMPTION","Reinforcement"))

    # plastering: if wall length exists, both sides are an assumption.
    if wall and wall.get("length_m",0)>0:
        pa=wall["length_m"]*RULES["default_wall_height_m"]*2
        pv=pa*RULES["plaster_thickness_m"]
        out += [item("Plaster Area",pa,"m²","Wall length × height × 2 faces","DERIVED+ASSUMPTION","Finishes"),
                item("Cement - Plaster",pv*RULES["plaster_cement_bags_per_m3"],"bags","Plaster volume × cement consumption","DERIVED+ASSUMPTION","Finishes"),
                item("Sand - Plaster",pv*RULES["plaster_sand_m3_per_m3"],"m³","Plaster volume × sand consumption","DERIVED+ASSUMPTION","Finishes"),
                item("Primer",pa*RULES["primer_litres_per_m2"],"L","Paint area × primer rate","DERIVED+ASSUMPTION","Painting"),
                item("Wall Putty",pa*RULES["putty_kg_per_m2"],"kg","Paint area × putty rate","DERIVED+ASSUMPTION","Painting"),
                item("Paint",pa*RULES["paint_litres_per_m2"],"L","Paint area × coverage rate","DERIVED+ASSUMPTION","Painting")]

    # Waterproofing when explicit area is detected.
    wp=_element(es,"Waterproofing")
    if wp and wp.get("area_m2",0)>0:
        out.append(item("Waterproofing",wp["area_m2"],"m²","Detected waterproofing area","DRAWING-DERIVED","Waterproofing"))
        out.append(item("Waterproofing Material",wp["area_m2"]*RULES["waterproofing_kg_per_m2"],"kg","Area × configured system consumption","DERIVED+ASSUMPTION","Waterproofing"))

    # De-duplicate same material names by summing quantities while preserving source/basis.
    merged={}
    for x in out:
        k=(x["material"],x["unit"])
        if k not in merged:merged[k]=dict(x)
        else:
            merged[k]["quantity"]=round(merged[k]["quantity"]+x["quantity"],3)
            if merged[k]["source"]!=x["source"]:merged[k]["source"]="MIXED"
            merged[k]["commercial"]=merged[k].get("commercial",True) and x.get("commercial",True)
    for x in merged.values():
        if x["material"].startswith(("Cement Equivalent -","Sand Equivalent -","Aggregate Equivalent -")):
            x["commercial"]=False
    return {"items":list(merged.values()),"rules":RULES,
            "warning":"Drawing-derived quantities are preferred. Reinforcement is exact only when reinforcement schedules/details are successfully extracted; otherwise it is explicitly marked ASSUMPTION. RMC is the procurement form of concrete; cement/sand/aggregate entries are shown as site-mix equivalents and must not be added to an RMC total.",
            "accuracy_note":"This is a quantity-takeoff estimator, not a structural design/code-compliance engine. Verify scale, dimensions, specifications and reinforcement schedules before procurement."}
