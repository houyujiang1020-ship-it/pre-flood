"""Build a reviewable Phase 2 package while keeping MapGIS-dependent gates closed."""
import argparse, hashlib, html, json, shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def write(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--run",required=True); a=ap.parse_args(); run=Path(a.run).resolve()
    phase1=read(ROOT/"runtime/acceptance/gate5-gt-20260912-01/damage_analysis.json")
    pop=read(ROOT/"data/acceptance/gate5-v1/population-reference.json")
    community={"schema_version":1,"status":"REFERENCE_PREPARATION","formal_gis_engine_required":"MapGIS",
      "source":{"source":"BKG VG250-EW 2024","source_url":"https://sgx.geodatenzentrum.de/wfs_vg250-ew","provider":"BKG / Statistisches Bundesamt","download_date":"2026-09-12","license":"Datenlizenz Deutschland – Namensnennung – Version 2.0","sha256":"86bd33e0548829d728f239f01db53e6616a7e4053d565df893d42ae0d158cb1a"},
      "global_unique":{"total_buildings":82,"affected_buildings":76,"total_roads":20,"affected_roads":14},
      "communities":[{"community_id":"07131017","community_name":"Dernau","admin_level":"Gemeinde","source_id":"vg250_gem.2940","aoi_coverage_fraction":1.0,"total_buildings":82,"affected_buildings":76,"total_roads":20,"affected_roads":14,"affected_road_length_m":2446.522,"population_total":1495,"estimated_affected_population":pop["estimated_affected_population"]}],
      "deduplication":"global road counts use unique source entity id; per-community road length uses intersected segments",
      "mapgis_runtime_verified":False}
    risk={"schema_version":1,"status":"BLOCKED","score":None,"level":None,"weights":{"flood":.30,"population":.25,"buildingDamage":.20,"roadAccessibility":.15,"medicalAccessibility":.10},"weights_source":"config/application.example.yaml and RiskCalculator.defaults",
      "available_traceable_inputs":{"population_estimate":pop["estimated_affected_population"],"affected_building_area_m2":12281.684,"total_building_area_m2":12628.097,"affected_road_length_m":2446.522,"total_road_length_m":2759.188},
      "missing_inputs":["approved flood indicator definition without continuous flood polygon","MapGIS-verified road accessibility indicator","real medical accessibility indicator","MapGIS reproduction of community/population intersections"],
      "reason":"RiskCalculator requires all five indicators; missing values are not zero."}
    damage=dict(phase1); damage.update({"run_id":run.name,"generated_at":datetime.now(timezone.utc).isoformat(),"communities":community["communities"],"population":pop,"risk":risk,"continuous_flood_area":None,"blocked_road_count":None,"damage_analysis_completed":False,"gate5_status":"BLOCKED"})
    damage["blockers"]=[{"role":"mapgis_gui_validation","status":"blocked","reason":"seven real MapGIS screenshots and desktop log are absent"},{"role":"mapgis_formal_spatial_analysis","status":"blocked","reason":"community and population intersections are reference preparation until reproduced by MapGIS"},{"role":"risk_inputs","status":"blocked","reason":"road/medical accessibility and an approved flood indicator remain unavailable"}]
    write(run/"community_analysis.json",community); write(run/"population_analysis.json",pop); write(run/"risk-breakdown.json",risk); write(run/"damage_analysis.json",damage)
    shutil.copy2(ROOT/"runtime/acceptance/gate5-gt-20260912-01/entity-validation.json",run/"entity-validation.json")
    rows="".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k,v in [("Community","Dernau (AGS 07131017)"),("Buildings","82 / affected 76"),("Roads","20 / affected 14"),("Affected building area","12281.684 m²"),("Affected road length","2446.522 m"),("Estimated population in AOI",pop["total_population_in_aoi_estimate"]),("Estimated affected population",pop["estimated_affected_population"]),("Risk","BLOCKED"),("Continuous flood area","N/A"),("Blocked roads","N/A")])
    report=f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>Gate 5 Phase 2</title><style>body{{font-family:'Microsoft YaHei',sans-serif;margin:32px}}th,td{{border:1px solid #aaa;padding:8px}}table{{border-collapse:collapse}}.blocked{{color:#a00}}</style><h1>GT VALIDATION · Gate 5 Phase 2</h1><p>run_id: {run.name}</p><p class='blocked'>BLOCKED：等待 MapGIS 正式空间分析、GUI 证据及完整风险指标。</p><table>{rows}</table><h2>来源</h2><p>BKG VG250-EW 2024 · BKG / Statistisches Bundesamt · Datenlizenz Deutschland – Namensnennung – Version 2.0</p><p>Destatis Zensus 2022 Bevölkerungszahl 100m-Gitter · Datenlizenz Deutschland – Namensnennung – Version 2.0</p><h2>人口方法</h2><p>{html.escape(pop['method'])}</p><p>该结果是面积加权估算，不是实际登记受灾人口。</p><p>对象级 flooded 标签不构成连续洪水面，也不证明道路封闭。</p></html>"
    (run/"report.html").write_text(report,encoding="utf-8"); (run/"damage_analysis.html").write_text(report,encoding="utf-8")
    print(json.dumps({"run":str(run),"status":"BLOCKED","estimated_affected_population":pop["estimated_affected_population"]},ensure_ascii=True))
if __name__=="__main__": main()
