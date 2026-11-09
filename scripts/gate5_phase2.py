"""Gate 5 Phase 2 aggregation and evidence utilities.

Spatial intersections are supplied by MapGIS runtime evidence. This module
validates and aggregates them without replacing MapGIS as the GIS engine.
"""
from __future__ import annotations
import hashlib, json, math
from pathlib import Path

WEIGHTS={"flood":.30,"population":.25,"buildingDamage":.20,"roadAccessibility":.15,"medicalAccessibility":.10}

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def require_source(record: dict) -> None:
    required=("source","source_url","provider","download_date","license","sha256")
    missing=[k for k in required if not record.get(k)]
    if missing: raise ValueError(f"source metadata missing: {missing}")

def aggregate_community(intersections: list[dict]) -> list[dict]:
    """Aggregate MapGIS-produced intersections; global IDs stay deduplicated."""
    out={}
    for row in intersections:
        cid=row.get("community_id"); eid=row.get("entity_id"); kind=row.get("kind")
        if not cid or not eid or kind not in {"building","road"}: raise ValueError("invalid MapGIS intersection row")
        target=out.setdefault(cid,{"community_id":cid,"community_name":row.get("community_name"),
            "building_ids":set(),"affected_building_ids":set(),"road_ids":set(),"affected_road_ids":set(),"affected_road_length_m":0.0})
        if kind=="building":
            target["building_ids"].add(eid)
            if row.get("affected") is True: target["affected_building_ids"].add(eid)
        else:
            target["road_ids"].add(eid)
            if row.get("affected") is True:
                target["affected_road_ids"].add(eid)
                length=row.get("intersection_length_m")
                if not isinstance(length,(int,float)) or not math.isfinite(length) or length<0: raise ValueError("invalid road intersection length")
                target["affected_road_length_m"]+=length
    result=[]
    for x in out.values():
        result.append({"community_id":x["community_id"],"community_name":x["community_name"],
            "total_buildings":len(x["building_ids"]),"affected_buildings":len(x["affected_building_ids"]),
            "total_roads":len(x["road_ids"]),"affected_roads":len(x["affected_road_ids"]),
            "affected_road_length_m":round(x["affected_road_length_m"],3)})
    return sorted(result,key=lambda x:x["community_id"])

def global_unique_counts(intersections: list[dict]) -> dict:
    return {f"{state}_{kind}s":len({r["entity_id"] for r in intersections if r["kind"]==kind and (state=="total" or r.get("affected") is True)})
            for kind in ("building","road") for state in ("total","affected")}

def population_grid_aggregate(cells: list[dict]) -> dict:
    """Aggregate MapGIS-attributed 100m cells; overlap_fraction is AOI share."""
    total=affected=0.0
    per={}
    for c in cells:
        pop=c.get("population"); frac=c.get("aoi_overlap_fraction"); affected_frac=c.get("affected_overlap_fraction")
        if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (pop,frac,affected_frac)): raise ValueError("invalid population cell")
        if pop<0 or not 0<=affected_frac<=frac<=1: raise ValueError("invalid population fractions")
        total+=pop*frac; affected+=pop*affected_frac
        cid=c["community_id"]; p=per.setdefault(cid,{"population_in_aoi":0.0,"estimated_affected_population":0.0})
        p["population_in_aoi"]+=pop*frac; p["estimated_affected_population"]+=pop*affected_frac
    return {"total_population_in_analysis_units":round(total,3),"estimated_affected_population":round(affected,3),
            "per_community":{k:{n:round(v,3) for n,v in x.items()} for k,x in sorted(per.items())}}

def area_weighted_population(population: float, affected_area: float, total_area: float) -> float:
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (population,affected_area,total_area)): raise ValueError("invalid population input")
    if population<0 or affected_area<0 or total_area<=0 or affected_area>total_area: raise ValueError("invalid area-weight estimate")
    return population*affected_area/total_area

def risk_breakdown(indicators: dict) -> dict:
    missing=[k for k in WEIGHTS if k not in indicators]
    if missing: raise ValueError(f"missing risk indicators: {missing}")
    components={}
    for key,weight in WEIGHTS.items():
        value=indicators[key]
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1: raise ValueError(f"invalid risk indicator: {key}")
        components[key]={"value":value,"weight":weight,"contribution":round(value*weight,9)}
    score=sum(x["contribution"] for x in components.values())
    level="LOW" if score<.25 else "MEDIUM" if score<.5 else "HIGH" if score<.75 else "EXTREME"
    return {"score":round(score,9),"level":level,"components":components,"weights_source":"RiskCalculator.defaults"}

def validate_gui_manifest(path: Path, root: Path) -> list[str]:
    errors=[]
    if not path.is_file(): return ["GUI evidence manifest missing"]
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("mode")!="GROUND_TRUTH_VALIDATION": errors.append("GUI mode is not GROUND_TRUTH_VALIDATION")
    required={f"screenshot-{i:02d}" for i in range(1,8)}
    seen=set()
    for item in data.get("screenshots",[]):
        key=Path(item.get("filename","")).stem; seen.add(key)
        candidate=(root/item.get("filename","")).resolve()
        if not candidate.is_file(): errors.append(f"missing screenshot: {item.get('filename')}"); continue
        if sha256(candidate)!=item.get("sha256"): errors.append(f"screenshot hash mismatch: {item.get('filename')}")
        if not item.get("timestamp") or not item.get("step") or not item.get("description"): errors.append(f"incomplete screenshot metadata: {item.get('filename')}")
    for key in sorted(required-seen): errors.append(f"required GUI evidence missing: {key}")
    return errors

def assert_report_sources(report_text: str, sources: list[dict]) -> None:
    for source in sources:
        require_source(source)
        for key in ("source","provider","license"):
            if str(source[key]) not in report_text: raise ValueError(f"report omits {key}: {source[key]}")

def verify_dataset_hashes(manifest: dict, base: Path) -> None:
    for item in manifest.get("inputs",[]):
        if item.get("path"):
            p=(base/item["path"]).resolve()
            if not p.is_file() or sha256(p)!=item.get("sha256"): raise ValueError(f"dataset hash mismatch: {item.get('role')}")
