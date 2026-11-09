"""Fail-closed validator for a Gate 5 acceptance run."""
import argparse, json
from pathlib import Path
from gate5_phase2 import validate_gui_manifest

def validate(run: Path) -> list[str]:
    errors=[]
    required=["damage_analysis.json","damage_analysis.html","entity-validation.json",
              "community_analysis.json","population_analysis.json","risk-breakdown.json",
              "environment.json","plugin-build-manifest.json","dataset-manifest.json",
              "gui-evidence-manifest.json"]
    for name in required:
        if not (run/name).is_file(): errors.append(f"missing artifact: {name}")
    if errors: return errors
    damage=json.loads((run/"damage_analysis.json").read_text(encoding="utf-8"))
    validation=json.loads((run/"entity-validation.json").read_text(encoding="utf-8"))
    if damage.get("analysis_mode") != "GROUND_TRUTH_VALIDATION": errors.append("wrong analysis_mode")
    if damage.get("measurements",{}).get("building_entities",0) < 20: errors.append("fewer than 20 buildings")
    if damage.get("measurements",{}).get("road_entities",0) < 20: errors.append("fewer than 20 roads")
    if validation.get("building_sample_count",0) < 20 or validation.get("road_sample_count",0) < 20: errors.append("insufficient entity samples")
    if damage.get("measurements",{}).get("continuous_flood_area_m2") is not None: errors.append("object labels misrepresented as continuous flood area")
    if damage.get("measurements",{}).get("blocked_roads") is not None: errors.append("flooded roads misrepresented as closures")
    if damage.get("risk",{}).get("status") != "COMPLETE": errors.append("risk inputs/results incomplete")
    if not validation.get("mapgis_gui_validated"): errors.append("MapGIS GUI validation missing")
    errors.extend(validate_gui_manifest(run/"gui-evidence-manifest.json",run))
    if damage.get("blockers"): errors.append("unresolved blockers remain")
    if damage.get("damage_analysis_completed") is not True: errors.append("damage_analysis_completed is not true")
    return errors

def main():
    p=argparse.ArgumentParser(); p.add_argument("run"); a=p.parse_args(); errors=validate(Path(a.run))
    print(json.dumps({"gate5_passed":not errors,"errors":errors},ensure_ascii=False,indent=2))
    raise SystemExit(0 if not errors else 2)
if __name__=="__main__": main()
