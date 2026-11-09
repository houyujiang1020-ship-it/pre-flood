"""Evidence gate: reports gaps and never turns development artifacts into a pass by inference."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path):
    if not path.is_file() or path.stat().st_size > 32_000_000:
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _latest(pattern: str, predicate=None):
    candidates = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        value = _read(path)
        if value is not None and (predicate is None or predicate(value)):
            return path
    return None


def audit(network=None, spatial=None, comparison=None, verification=None):
    checks = []
    validated_at = datetime.now(timezone.utc).isoformat()
    def check(key, passed, evidence, requirement):
        paths = [str(evidence)] if evidence else []
        exists = bool(paths) and all(Path(p).is_file() for p in paths)
        passed = bool(passed) and exists
        checks.append({'key': key, 'name': key, 'passed': passed,
                       'status': 'pass' if passed else ('fail' if exists else 'blocked'),
                       'evidence': paths, 'evidence_path': paths[0] if paths else None,
                       'validated_at': validated_at, 'notes': requirement,
                       'requirement': requirement})

    if not network:
        discovered = _latest('data/demo/dispatch-spacenet8-endpoint-v2/mapgis-*/network-build.json',
                             lambda value: value.get('native_network_created') is True)
        network = str(discovered) if discovered else None
    if not spatial:
        # Desktop acceptance writes <output>/<job-id>/mapgis-<uuid>/spatial-result.json,
        # while manual runs may use a shallower layout.  Recursive discovery
        # covers both and still selects by the evidence file's modification time.
        discovered = _latest('outputs/**/spatial-result.json')
        spatial = str(discovered) if discovered else None
    net = _read(Path(network)) if network else None
    net_dir = Path(network).parent if network else None
    preparation = _read(net_dir/'dispatch-preparation.json') if net_dir else None
    dispatch = _read(net_dir/'exercise-dispatch.json') if net_dir else None
    check('native_topology', net and net.get('native_network_created') is True, network,
          'MapGIS native topology, persisted network, nonempty nodes/edges and complete source-edge mappings')
    impedance = bool(preparation and (preparation.get('length_weight_verified') is True or (
        preparation.get('native_geometry_lengths_verified') is True
        and preparation.get('native_minimum_distance_mode_ready') is True
        and preparation.get('minute_defaults_verified') is True
        and preparation.get('speed_is_measured') is False)))
    check('verified_routing_impedance', impedance,
          net_dir/'dispatch-preparation.json' if net_dir else None,
          'Either complete named native weight, or verified projected geometry with MapGIS native minimum-distance mode and uniform exercise speed')
    check('exercise_closure_routes', dispatch and dispatch.get('exercise_routes_verified') is True,
          net_dir/'exercise-dispatch.json' if net_dir else None,
          'Resource/destination binding, baseline route, intersecting closure and blocked-edge avoidance')

    spatial_data = _read(Path(spatial)) if spatial else None
    check('map_rendering', spatial_data and spatial_data.get('map_rendering_verified') is True, spatial,
          'Georeferenced before/after/result layers visually accepted in MapGIS')
    check('damage_analysis', spatial_data and spatial_data.get('damage_analysis_completed') is True, spatial,
          'Entity damage, flood extent/area and required risk indicators verified, not pixel proxies')

    comparison_data = _read(Path(comparison)) if comparison else None
    independent = bool(comparison_data and comparison_data.get('independent_region_test') is True)
    accuracy = bool(comparison_data and comparison_data.get('accuracy_acceptance_passed') is True
                    and comparison_data.get('production_ready') is True and independent)
    check('independent_model_accuracy', accuracy, comparison,
          'Declared acceptance thresholds passed on a held-out independent region with production_ready=true')
    verify_data = _read(Path(verification)) if verification else None
    check('production_inference', verify_data and verify_data.get('inference_verified') is True
          and verify_data.get('accuracy_verified') is True
          and verify_data.get('model', {}).get('production_ready') is True, verification,
          'CUDA/API inference uses the same accuracy-accepted production checkpoint')

    # These require user/organizer-provided evidence and may never be inferred from fictional fixtures.
    check('real_resource_ledger', False, None, 'Verified real or organizer-approved resource ledger; exercise assets do not qualify')
    check('operational_acceptance', False, None, 'Signed native business acceptance covering traffic rules, reports and failure cases')
    passed = all(item['passed'] for item in checks)
    return {'schema_version': 2, 'validated_at': validated_at, 'competition_ready': passed, 'passed': sum(c['passed'] for c in checks),
            'total': len(checks), 'checks': checks,
            'warning': 'A failed gate is not zero impact; missing evidence remains unknown. No operational authorization is granted.'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--network'); p.add_argument('--spatial')
    p.add_argument('--comparison',default=str(ROOT/'models/checkpoints/balanced18-comparison.json'))
    p.add_argument('--verification',default=str(ROOT/'data/outputs/balanced18-api-20260828/verification.json'))
    p.add_argument('--output',default=str(ROOT/'runtime/competition-readiness.json'))
    args=p.parse_args()
    report=audit(args.network,args.spatial,args.comparison,args.verification)
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out.resolve()),'competition_ready':report['competition_ready'],
                      'passed':report['passed'],'total':report['total']},ensure_ascii=True))
    raise SystemExit(0 if report['competition_ready'] else 2)


if __name__ == '__main__': main()
