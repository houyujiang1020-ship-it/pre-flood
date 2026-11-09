"""Extract the official Zensus 2022 100m cells for the fixed Gate 5 AOI."""
from __future__ import annotations
import csv, hashlib, json, zipfile
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import box, mapping, shape
from shapely.ops import transform

ROOT=Path(__file__).resolve().parents[1]
ZIP=ROOT/"data/sources/population/destatis-zensus2022-grid/Zensus2022_Bevoelkerungszahl.zip"
CSV_NAME="Zensus2022_Bevoelkerungszahl_100m-Gitter.csv"
AOI=ROOT/"data/acceptance/gate5-v1/aoi.json"
LABELS=ROOT/"data/acceptance/gate5-v1/object-labels.geojson"
OUT=ROOT/"data/acceptance/gate5-v1"

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    aoi=json.loads(AOI.read_text(encoding="utf-8")); b=aoi["wgs84_bbox"]
    to3035=Transformer.from_crs("OGC:CRS84","EPSG:3035",always_xy=True)
    aoi_geom=transform(to3035.transform,box(*b)); minx,miny,maxx,maxy=aoi_geom.bounds
    labels=json.loads(LABELS.read_text(encoding="utf-8"))
    buildings=[]
    for f in labels["features"]:
        if f["properties"].get("building") is not None:
            buildings.append((transform(to3035.transform,shape(f["geometry"])),f["properties"].get("flooded")=="yes"))
    rows=[]
    with zipfile.ZipFile(ZIP) as archive, archive.open(CSV_NAME) as raw:
        import io
        reader=csv.DictReader(io.TextIOWrapper(raw,encoding="utf-8-sig"),delimiter=";")
        for row in reader:
            x=float(row["x_mp_100m"]); y=float(row["y_mp_100m"])
            if minx-50<=x<=maxx+50 and miny-50<=y<=maxy+50:
                cell=box(x-50,y-50,x+50,y+50); overlap=cell.intersection(aoi_geom)
                if overlap.is_empty: continue
                total_area=affected_area=0.0
                for building,affected in buildings:
                    area=building.intersection(cell).area
                    total_area+=area
                    if affected: affected_area+=area
                ratio=affected_area/total_area if total_area>0 else 0.0
                pop=int(row["Einwohner"])
                rows.append({"grid_id":row["GITTER_ID_100m"],"x":x,"y":y,"population":pop,
                    "aoi_overlap_fraction":overlap.area/10000.0,"affected_building_area_ratio":ratio,
                    "estimated_affected_fraction":overlap.area/10000.0*ratio,"geometry":cell})
    rows.sort(key=lambda r:r["grid_id"])
    subset=OUT/"population-grid-100m.csv"
    with subset.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["grid_id","x","y","population","aoi_overlap_fraction","affected_building_area_ratio","estimated_affected_fraction"])
        writer.writeheader(); writer.writerows([{k:v for k,v in r.items() if k!="geometry"} for r in rows])
    geo={"type":"FeatureCollection","name":"Gate5 Zensus 2022 100m population","crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:EPSG::3035"}},
         "features":[{"type":"Feature","id":r["grid_id"],"properties":{k:v for k,v in r.items() if k not in {"geometry","x","y"}},"geometry":mapping(r["geometry"])} for r in rows]}
    gp=OUT/"population-grid-100m.geojson"; gp.write_text(json.dumps(geo,ensure_ascii=False,indent=2),encoding="utf-8")
    total=sum(r["population"]*r["aoi_overlap_fraction"] for r in rows)
    affected=sum(r["population"]*r["estimated_affected_fraction"] for r in rows)
    summary={"schema_version":1,"status":"REFERENCE_PREPARATION","formal_gis_engine_required":"MapGIS",
        "source":"Destatis Zensus 2022 Bevölkerungszahl 100m-Gitter","source_year":2022,"population_unit":"persons",
        "method":"population_grid_cell × AOI area fraction × affected/all labeled building footprint ratio in the cell",
        "formula":"sum(population_cell * AOI_overlap_fraction * affected_building_area_cell / all_building_area_cell)",
        "assumptions":["population is uniform within each 100m cell for AOI-edge allocation","labeled building footprint ratio proxies affected population within each cell","cells without labeled buildings receive zero affected allocation"],
        "limitations":["estimate is not a resident registry count","privacy protection and grid resolution limit precision","MapGIS must reproduce intersections for formal Gate 5 acceptance"],
        "grid_cell_count":len(rows),"total_population_in_aoi_estimate":round(total,3),"estimated_affected_population":round(affected,3),
        "per_community":[{"community_id":"07131017","community_name":"Dernau","population_total_2024":1495,
                          "population_in_aoi_estimate_2022":round(total,3),"estimated_affected_population_2022":round(affected,3)}],
        "source_zip_sha256":digest(ZIP),"subset_csv_sha256":digest(subset),"grid_geojson_sha256":digest(gp),
        "method_config":"config/gate5_population_method.yaml","method_config_sha256":digest(ROOT/"config/gate5_population_method.yaml")}
    (OUT/"population-reference.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=True,indent=2))

if __name__=="__main__": main()
