import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'validate_case_inputs.py'
SPEC = importlib.util.spec_from_file_location('validate_case_inputs', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_demo_bundle_reports_grid_mismatch_without_bypassing_ready():
    result = MODULE.audit(Path(__file__).resolve().parents[1] / 'DemoDataset_Final/06_scenario.json')
    assert result['files_valid'] is True
    assert result['spatial_valid'] is False
    assert result['data_complete'] is False
    assert result['host_verified'] is False
    assert result['scenario_ready'] is False
    assert any('pre/post image grids differ' in issue for issue in result['issues'])


def test_formal_template_with_missing_sources_is_not_ready():
    result = MODULE.audit(Path(__file__).resolve().parents[1] / 'submission/competition-scenario.template.json')
    assert result['files_valid'] is False
    assert result['scenario_ready'] is False
    assert 'missing scenario' in result['issues']


def test_declared_ready_cannot_override_missing_data(tmp_path):
    path = tmp_path / 'case.json'
    path.write_text(json.dumps({'ready': True, 'data_type': 'REAL', 'sources': {}, 'scenario': None}))
    result = MODULE.audit(path)
    assert result['declared_ready'] is True
    assert result['files_valid'] is False
    assert result['scenario_ready'] is False
    assert result['data_complete'] is False
