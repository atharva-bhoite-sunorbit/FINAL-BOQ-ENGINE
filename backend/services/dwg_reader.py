
import os, json, subprocess, tempfile
from pathlib import Path

class DWGReader:
    """Multi-path DWG reader for Project 3.

    Priority:
      1) LibreDWG JSON for metadata/type codes
      2) LibreDWG GeoJSON for geometry
      3) LibreDWG dwg2dxf + ezdxf for layers, blocks, dimensions and CAD geometry
    """

    def __init__(self):
        self.root=Path(__file__).resolve().parents[2]

    def locate(self,name="dwgread.exe"):
        configured=os.getenv("LIBREDWG_DWGREAD")
        candidates=[Path(configured)] if configured and name=="dwgread.exe" else []
        tool=self.root/"tools"/"LibreDWG"
        candidates += [tool/name, tool/"bin"/name]
        for folder in os.getenv("PATH","").split(os.pathsep):
            if folder:candidates.append(Path(folder)/name)
        for p in candidates:
            if p.exists() and p.is_file():return p
        return None

    def _run(self,args,timeout=300):
        exe=Path(args[0])
        p=subprocess.run(args,capture_output=True,text=True,encoding="utf-8",errors="replace",
                         timeout=timeout,cwd=str(exe.parent))
        return p.returncode,p.stdout or "",p.stderr or ""

    def _json(self,text):
        text=(text or "").strip()
        if not text:return None
        try:return json.loads(text)
        except json.JSONDecodeError:
            a,b=text.find("{"),text.rfind("}")
            if a>=0 and b>a:
                try:return json.loads(text[a:b+1])
                except json.JSONDecodeError:return None
        return None

    def _parse_dxf(self,path):
        try:
            import ezdxf
        except ImportError:
            return None, "ezdxf is not installed"
        try:
            doc=ezdxf.readfile(str(path))
            entities=[]; layers=[]
            try: layers=[x.dxf.name for x in doc.layers]
            except Exception: pass
            for e in doc.modelspace():
                typ=e.dxftype(); layer=getattr(e.dxf,"layer","")
                base={"type":typ,"layer":layer}
                try:
                    if typ=="LINE":
                        base.update(start=list(e.dxf.start),end=list(e.dxf.end))
                    elif typ=="LWPOLYLINE":
                        base.update(points=[[p[0],p[1]] for p in e.get_points("xy")],
                                   closed=bool(e.closed))
                    elif typ=="POLYLINE":
                        base.update(points=[[v.dxf.location.x,v.dxf.location.y] for v in e.vertices],
                                   closed=bool(e.is_closed))
                    elif typ=="CIRCLE":
                        base.update(center=list(e.dxf.center),radius=float(e.dxf.radius))
                    elif typ=="ARC":
                        base.update(center=list(e.dxf.center),radius=float(e.dxf.radius),
                                    start_angle=float(e.dxf.start_angle),end_angle=float(e.dxf.end_angle))
                    elif typ in ("TEXT","MTEXT"):
                        base["text"]=e.dxf.text
                    elif typ=="INSERT":
                        base["blockname"]=e.dxf.name
                        base["insert_point"]=list(e.dxf.insert)
                    elif typ=="DIMENSION":
                        base["measurement"]=float(e.get_measurement())
                        base["text"]=getattr(e.dxf,"text","")
                        base["dimtype"]=int(getattr(e.dxf,"dimtype",0))
                    elif typ=="HATCH":
                        # Boundary geometry can be complex; retain layer/type for semantic detection.
                        base["pattern"]=getattr(e.dxf,"pattern_name","")
                    else:
                        # retain common layer/type entities for diagnostics
                        pass
                except Exception as ex:
                    base["parse_warning"]=str(ex)
                entities.append(base)
            # block definitions are useful semantic evidence
            blocks=[]
            try:
                for b in doc.blocks:
                    if b.name and not b.name.startswith("*"):blocks.append(b.name)
            except Exception:pass
            units=None
            try:units=int(doc.header.get("$INSUNITS",0))
            except Exception:units=None
            return {"entities":entities,"layers":layers,"blocks":blocks,"units":units}, None
        except Exception as ex:
            return None,str(ex)

    def extract(self,dwg_path:Path):
        read=self.locate("dwgread.exe")
        if not read:raise RuntimeError("LibreDWG dwgread.exe not found.")
        result={"format":"multi","data":{},"diagnostics":[]}

        for option in ("JSON","minJSON"):
            code,out,err=self._run([str(read),"-O",option,str(dwg_path)])
            data=self._json(out)
            result["diagnostics"].append({"parser":f"dwgread {option}","return_code":code,
                "stdout_bytes":len(out.encode("utf8","ignore")),"stderr":err[-1200:],
                "success":data is not None})
            if data is not None:
                result["data"]["json"]=data;break

        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"drawing.geojson"
            code,stdout,stderr=self._run([str(read),"-OGeoJSON","-o",str(out),str(dwg_path)])
            data=None
            if out.exists() and out.stat().st_size:
                try:data=json.loads(out.read_text(encoding="utf8"))
                except Exception:pass
            result["diagnostics"].append({"parser":"dwgread GeoJSON","return_code":code,
                "stdout_bytes":len(stdout.encode("utf8","ignore")),"stderr":stderr[-1200:],
                "success":data is not None})
            if data is not None:result["data"]["geojson"]=data

        dxf_exe=self.locate("dwg2dxf.exe")
        if dxf_exe:
            with tempfile.TemporaryDirectory() as td:
                dxf=Path(td)/"drawing.dxf"
                code,stdout,stderr=self._run([str(dxf_exe),"-o",str(dxf),str(dwg_path)])
                ok=dxf.exists() and dxf.stat().st_size>0
                result["diagnostics"].append({"parser":"dwg2dxf","return_code":code,
                    "stdout_bytes":len(stdout.encode("utf8","ignore")),"stderr":stderr[-1200:],
                    "success":ok})
                if ok:
                    parsed,msg=self._parse_dxf(dxf)
                    result["diagnostics"].append({"parser":"ezdxf structured DXF","return_code":0 if parsed else 1,
                        "stdout_bytes":0,"stderr":msg or "","success":parsed is not None})
                    if parsed is not None:result["data"]["dxf"]=parsed

        if not result["data"]:
            raise RuntimeError("LibreDWG could not extract usable data from this DWG. Check parser diagnostics.")
        return result
