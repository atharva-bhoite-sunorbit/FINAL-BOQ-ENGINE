
import math, re
from collections import Counter, defaultdict

PATTERNS = {
    "Walls": [r"\bwall\b", r"\bwalls\b", r"a[-_ ]?wall", r"masonry", r"brick", r"aac", r"block", r"partition", r"arch[-_ ]?wall"],
    "Doors": [r"\bdoor\b", r"\bdoors\b", r"a[-_ ]?door", r"door[-_ ]?tag", r"\bdr[-_ ]?\d", r"doorframe", r"door_frame"],
    "Windows": [r"\bwindow\b", r"\bwindows\b", r"a[-_ ]?window", r"glazing", r"\bwin[-_ ]?\d", r"windowframe"],
    "Columns": [r"\bcolumn\b", r"\bcolumns\b", r"s[-_ ]?column", r"struct[-_ ]?col", r"\bcol[-_ ]?\d"],
    "Beams": [r"\bbeam\b", r"\bbeams\b", r"s[-_ ]?beam", r"struct[-_ ]?beam", r"\bb[-_ ]?\d"],
    "Slabs": [r"\bslab\b", r"\bslabs\b", r"floor[-_ ]?slab", r"roof[-_ ]?slab", r"rcc[-_ ]?slab"],
    "Flooring": [r"\bflooring\b", r"floor[-_ ]?finish", r"\btile\b", r"\btiles\b", r"finish"],
    "Footings": [r"\bfooting\b", r"\bfootings\b", r"foundation", r"\bfnd\b", r"pad[-_ ]?foot"],
    "Stairs": [r"\bstair\b", r"\bstairs\b", r"staircase", r"stair[-_ ]?flight", r"riser", r"tread"],
    "Plaster": [r"\bplaster\b", r"plastering"],
    "Ceiling": [r"\bceiling\b", r"false[-_ ]?ceiling", r"gypsum"],
    "Waterproofing": [r"waterproof", r"wp[-_ ]?membrane"],
    "Painting": [r"\bpaint\b", r"painting", r"putty", r"primer"],
}

TYPE_NAMES = {
    1:"TEXT",2:"ATTRIB",3:"ATTDEF",4:"BLOCK",5:"ENDBLK",6:"SEQEND",7:"INSERT",8:"MINSERT",
    10:"VERTEX_2D",11:"VERTEX_3D",12:"VERTEX_MESH",13:"VERTEX_PFACE",14:"VERTEX_PFACE_FACE",
    15:"POLYLINE_2D",16:"POLYLINE_3D",17:"ARC",18:"CIRCLE",19:"LINE",
    20:"DIMENSION_ORDINATE",21:"DIMENSION_LINEAR",22:"DIMENSION_ALIGNED",23:"DIMENSION_ANG3PT",
    24:"DIMENSION_ANG2LN",25:"DIMENSION_RADIUS",26:"DIMENSION_DIAMETER",27:"POINT",28:"3DFACE",
    29:"POLYLINE_PFACE",30:"POLYLINE_MESH",31:"SOLID",32:"TRACE",33:"SHAPE",34:"VIEWPORT",
    35:"ELLIPSE",36:"SPLINE",37:"REGION",38:"3DSOLID",39:"BODY",40:"RAY",41:"XLINE",
    42:"DICTIONARY",43:"OLEFRAME",44:"MTEXT",45:"LEADER",46:"TOLERANCE",47:"MLINE",77:"LWPOLYLINE",78:"HATCH"
}

def _text(x):
    if x is None: return ""
    if isinstance(x,str): return x
    if isinstance(x,(int,float)): return str(x)
    if isinstance(x,list): return " ".join(_text(v) for v in x)
    if isinstance(x,dict): return " ".join(f"{k} {_text(v)}" for k,v in x.items())
    return str(x)

def _num(x):
    try: return float(x)
    except (TypeError,ValueError): return None

def _point(x):
    if isinstance(x,(list,tuple)) and len(x)>=2:
        a,b=_num(x[0]),_num(x[1])
        if a is not None and b is not None: return a,b
    if isinstance(x,dict):
        for a,b in (("x","y"),("X","Y"),("x_coordinate","y_coordinate")):
            if a in x and b in x:
                p=_point([x[a],x[b]])
                if p:return p
        for k in ("point","position","center","start","end","start_point","end_point","first_point","second_point"):
            if k in x:
                p=_point(x[k])
                if p:return p
    return None

def _points(o):
    if not isinstance(o,dict): return []
    for key in ("points","vertices","vertexes","coords","coordinates"):
        v=o.get(key)
        if isinstance(v,list):
            out=[]
            for q in v:
                p=_point(q)
                if p: out.append(p)
            if len(out)>=2:return out
    return []

def _line(o):
    for a,b in (("start","end"),("start_point","end_point"),("startPoint","endPoint"),("p1","p2"),("point1","point2")):
        if a in o and b in o:
            p1,p2=_point(o[a]),_point(o[b])
            if p1 and p2:return math.hypot(p2[0]-p1[0],p2[1]-p1[1])
    for k in ("length","length_m","distance"):
        n=_num(o.get(k))
        if n is not None:return abs(n)
    return 0.0

def _poly_len(ps,closed=False):
    s=sum(math.hypot(ps[i][0]-ps[i-1][0],ps[i][1]-ps[i-1][1]) for i in range(1,len(ps)))
    if closed and len(ps)>2:s+=math.hypot(ps[0][0]-ps[-1][0],ps[0][1]-ps[-1][1])
    return s

def _area(ps):
    if len(ps)<3:return 0.0
    return abs(sum(ps[i][0]*ps[(i+1)%len(ps)][1]-ps[(i+1)%len(ps)][0]*ps[i][1] for i in range(len(ps)))/2)

def _type_name(o):
    raw=o.get("type")
    if isinstance(raw,str):
        s=raw.upper().replace(" ","_")
        return s
    n=_num(raw)
    if n is not None:return TYPE_NAMES.get(int(n),f"TYPE_{int(n)}")
    for k in ("entity","object","objecttype","entity_type"):
        if o.get(k):return str(o[k]).upper()
    return "UNKNOWN"

def _walk_entity_dicts(root):
    out=[]; seen=set()
    def rec(x):
        if isinstance(x,dict):
            typ=x.get("entity") or x.get("object")
            if typ not in (None,"") or ("type" in x and ("handle" in x or "index" in x)):
                if id(x) not in seen:
                    seen.add(id(x));out.append(x)
            for v in x.values():rec(v)
        elif isinstance(x,list):
            for v in x:rec(v)
    rec(root)
    return out

def _collect_strings(x):
    out=[]
    if isinstance(x,str):out.append(x)
    elif isinstance(x,dict):
        for v in x.values():out.extend(_collect_strings(v))
    elif isinstance(x,list):
        for v in x:out.extend(_collect_strings(v))
    return out

def _semantic(blob):
    s=blob.lower()
    scores={}
    for name,pats in PATTERNS.items():
        score=sum(1 for p in pats if re.search(p,s,re.I))
        if score:scores[name]=score
    return max(scores,key=scores.get) if scores else None

def _dimension_values(text):
    # Captures common CAD schedule strings: 230x450, 300 X 600, 4-16Ø, 8@150.
    vals=[]
    for a,b in re.findall(r'(?<!\d)(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)(?!\d)',text):
        vals.append((float(a),float(b)))
    return vals

def _geo_metrics(g):
    if not isinstance(g,dict):return 0.0,0.0
    typ,c=g.get("type"),g.get("coordinates")
    if typ=="Point":return 0.0,0.0
    if typ=="LineString":
        ps=[_point(x) for x in c or []];ps=[p for p in ps if p]
        return _poly_len(ps),0.0
    if typ=="MultiLineString":
        return sum(_geo_metrics({"type":"LineString","coordinates":x})[0] for x in c or []),0.0
    if typ=="Polygon":
        if not c:return 0.0,0.0
        rings=[]
        for ring in c:
            ps=[_point(x) for x in ring];ps=[p for p in ps if p]
            rings.append(_area(ps))
        return 0.0,max(0.0,rings[0]-sum(rings[1:])) if rings else 0.0
    if typ=="MultiPolygon":
        return 0.0,sum(_geo_metrics({"type":"Polygon","coordinates":p})[1] for p in c or [])
    if typ=="GeometryCollection":
        vals=[_geo_metrics(x) for x in g.get("geometries",[])]
        return sum(v[0] for v in vals),sum(v[1] for v in vals)
    return 0.0,0.0

def _stats():
    return {"count":0,"length":0.0,"area":0.0,"layers":set(),"basis":set(),"dims":[],"text":[]}

def _consume(st,name,count=1,length=0,area=0,layer=None,basis="metadata",text=""):
    s=st[name];s["count"]+=max(0,int(count));s["length"]+=max(0,float(length or 0));s["area"]+=max(0,float(area or 0))
    if layer:s["layers"].add(str(layer))
    s["basis"].add(basis)
    if text:
        s["text"].extend([x for x in _collect_strings(text) if x.strip()][:20])
        s["dims"].extend(_dimension_values(_text(text))[:10])

def _analyze_json(data):
    st=defaultdict(_stats);types=Counter();layers=set();all_text=[];entities=_walk_entity_dicts(data)
    for o in entities:
        typ=_type_name(o);types[typ]+=1
        layer=o.get("layer") or o.get("layer_name") or o.get("Layer")
        if layer is not None:layers.add(_text(layer))
        strings=_collect_strings(o); blob=" ".join([_text(layer)]+strings)
        all_text.extend(strings[:10])
        semantic=_semantic(blob)
        length=area=0.0
        if typ=="LINE":length=_line(o)
        elif typ in ("LWPOLYLINE","POLYLINE_2D","POLYLINE_3D","MLINE"):
            ps=_points(o);closed=bool(o.get("closed") or o.get("is_closed") or o.get("closed_flag"))
            length=_poly_len(ps,closed);area=_area(ps) if closed else 0
        elif typ=="CIRCLE":
            r=_num(o.get("radius")); length=2*math.pi*abs(r) if r is not None else 0; area=math.pi*r*r if r is not None else 0
        elif typ=="ARC":
            r=_num(o.get("radius"));a1=_num(o.get("start_angle"));a2=_num(o.get("end_angle"))
            if r is not None and a1 is not None and a2 is not None:length=abs(r*math.radians(a2-a1))
        else:
            ps=_points(o)
            if ps:
                closed=bool(o.get("closed") or o.get("is_closed") or o.get("closed_flag"))
                length=_poly_len(ps,closed);area=_area(ps) if closed else 0
            length=max(length,_line(o))
            for k in ("area","area_m2"):
                if _num(o.get(k)) is not None:area=max(area,abs(_num(o[k])))
        if semantic:_consume(st,semantic,1,length,area,layer,"JSON",o)
    return st,types,layers,len(entities),all_text

def _features(data):
    if not isinstance(data,dict):return []
    if isinstance(data.get("features"),list):return [x for x in data["features"] if isinstance(x,dict)]
    out=[]
    for v in data.values():
        if isinstance(v,dict) and isinstance(v.get("features"),list):out.extend(v["features"])
    return [x for x in out if isinstance(x,dict)]

def _analyze_geo(data):
    st=defaultdict(_stats);layers=set();features=_features(data);all_text=[]
    for f in features:
        props=f.get("properties") or {};layer=props.get("layer") or props.get("Layer") or props.get("layer_name")
        if layer:layers.add(_text(layer))
        blob=" ".join(_collect_strings(props));all_text.extend(_collect_strings(props)[:10]);semantic=_semantic(blob)
        length,area=_geo_metrics(f.get("geometry"))
        if semantic:_consume(st,semantic,1,length,area,layer,"GeoJSON",props)
    return st,layers,len(features),all_text

def _find_units(data):
    vals=[]
    def rec(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if str(k).lower() in {"units","insunits","$insunits","drawing_units","unit"} and v not in (None,""):vals.append(_text(v))
                rec(v)
        elif isinstance(x,list):
            for v in x:rec(v)
    rec(data)
    return vals[0] if vals else None

def _merge(a,b,name):
    if not a and not b:return None
    a=a or _stats();b=b or _stats()
    return {
        "name":name,
        "count":max(a["count"],b["count"]),
        "length_m":round(b["length"] if b["length"]>0 else a["length"],3),
        "area_m2":round(b["area"] if b["area"]>0 else a["area"],3),
        "volume_m3":0.0,
        "layers":sorted(a["layers"]|b["layers"]),
        "detection_basis":"+ ".join(sorted(a["basis"]|b["basis"])),
        "dimension_hints":a["dims"][:10]+b["dims"][:10],
        "text_hints":(a["text"][:10]+b["text"][:10])[:20]
    }


def _analyze_dxf(data):
    st=defaultdict(_stats); types=Counter(); layers=set(); text=[]
    if not isinstance(data,dict): return st,types,layers,0,text
    for o in data.get("entities",[]):
        if not isinstance(o,dict): continue
        typ=str(o.get("type","UNKNOWN")).upper(); types[typ]+=1
        layer=o.get("layer","")
        if layer: layers.add(str(layer))
        strings=_collect_strings(o); text.extend(strings[:10])
        blob=" ".join([_text(layer)]+strings+[_text(o.get("blockname",""))])
        semantic=_semantic(blob)
        length=area=0.0
        if typ=="LINE": length=_line(o)
        elif typ in ("LWPOLYLINE","POLYLINE"):
            ps=_points(o); closed=bool(o.get("closed"))
            length=_poly_len(ps,closed); area=_area(ps) if closed else 0
        elif typ=="CIRCLE":
            r=_num(o.get("radius")); length=2*math.pi*abs(r) if r is not None else 0; area=math.pi*r*r if r is not None else 0
        elif typ=="ARC":
            r=_num(o.get("radius")); a1=_num(o.get("start_angle")); a2=_num(o.get("end_angle"))
            if r is not None and a1 is not None and a2 is not None:length=abs(r*math.radians(a2-a1))
        elif typ=="HATCH":
            area=_num(o.get("area")) or 0
        if semantic:_consume(st,semantic,1,length,area,layer,"DXF",o)
    return st,types,layers,len(data.get("entities",[])),text


def analyze_dwg(cad):
    data=cad.get("data",cad) if isinstance(cad,dict) else cad
    jd=data.get("json") if isinstance(data,dict) else None
    gd=data.get("geojson") if isinstance(data,dict) else None
    js,jtypes,jlayers,jcount,jtext=_analyze_json(jd) if jd is not None else (defaultdict(_stats),Counter(),set(),0,[])
    gs,glayers,gcount,gtext=_analyze_geo(gd) if gd is not None else (defaultdict(_stats),set(),0,[])
    dd=data.get("dxf") if isinstance(data,dict) else None
    ds,dtypes,dlayers,dcount,dtext=_analyze_dxf(dd) if dd is not None else (defaultdict(_stats),Counter(),set(),0,[])
    elements=[]
    for name in PATTERNS:
        # Prefer geometry from GeoJSON, then DXF, then JSON.
        e=_merge(js.get(name),gs.get(name),name)
        if dd is not None:
            de=ds.get(name)
            if de:
                if e is None: e=_merge(de,None,name)
                else:
                    if e["length_m"]==0 and de["length"]>0:e["length_m"]=round(de["length"],3)
                    if e["area_m2"]==0 and de["area"]>0:e["area_m2"]=round(de["area"],3)
                    e["count"]=max(e["count"],de["count"])
                    e["layers"]=sorted(set(e["layers"])|de["layers"])
                    e["detection_basis"]+=" + DXF"
                    e["dimension_hints"]=(e.get("dimension_hints") or [])+de["dims"][:10]
                    e["text_hints"]=((e.get("text_hints") or [])+de["text"][:10])[:20]
        if e:elements.append(e)
    notes=[]
    if not jd:notes.append("LibreDWG JSON output unavailable.")
    if not gd:notes.append("LibreDWG GeoJSON output unavailable; measurable geometry may be incomplete.")
    if not elements:notes.append("No semantic construction elements detected. Check layer/block/text metadata or use a drawing containing construction labels.")
    if not any(e["length_m"] or e["area_m2"] for e in elements):notes.append("No measurable geometry linked to detected elements; quantities requiring dimensions will use configured assumptions.")
    return {
        "entities":max(jcount,gcount,dcount),"layers":len(jlayers|glayers|dlayers),
        "layer_names":sorted(jlayers|glayers|dlayers),
        "units":_find_units(jd) or "Unitless (scale must be verified)",
        "element_types":len(elements),"elements":elements,
        "entity_types":dict((jtypes+dtypes).most_common(40)),
        "diagnostics":cad.get("diagnostics",[]) if isinstance(cad,dict) else [],
        "notes":notes,
        "text_hints":(jtext+gtext+dtext)[:150]
    }
