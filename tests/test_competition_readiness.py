import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('readiness',ROOT/'scripts/audit_competition_readiness.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


def write(path,value): path.write_text(json.dumps(value),encoding='utf-8'); return path


def test_rejects_missing_and_exercise_only_evidence(tmp_path):
    network=write(tmp_path/'network-build.json',{'native_network_created':True})
    write(tmp_path/'dispatch-preparation.json',{'length_weight_verified':True})
    write(tmp_path/'exercise-dispatch.json',{'exercise_routes_verified':True})
    report=module.audit(network=network)
    assert not report['competition_ready']
    assert next(c for c in report['checks'] if c['key']=='native_topology')['passed']
    assert not next(c for c in report['checks'] if c['key']=='real_resource_ledger')['passed']


def test_same_region_accuracy_can_never_pass(tmp_path):
    comparison=write(tmp_path/'comparison.json',{'production_ready':True,'accuracy_acceptance_passed':True,
                                                  'independent_region_test':False})
    report=module.audit(comparison=comparison)
    assert not next(c for c in report['checks'] if c['key']=='independent_model_accuracy')['passed']


def test_malformed_evidence_fails_closed(tmp_path):
    bad=tmp_path/'bad.json'; bad.write_text('{',encoding='utf-8')
    report=module.audit(network=bad,spatial=bad,comparison=bad,verification=bad)
    assert report['passed']==0 and report['total']==9


def test_schema_requires_existing_evidence_and_timestamps(tmp_path):
    bad=write(tmp_path/'array.json', [])
    report=module.audit(network=bad,spatial=bad,comparison=bad,verification=bad)
    for check in report['checks']:
        assert isinstance(check['evidence'],list)
        assert check['validated_at'] and check['name'] and check['notes']
        assert check['status'] in ('pass','fail','blocked')
        assert not check['passed']
