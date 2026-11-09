import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_dispatch',ROOT/'scripts/prepare_dispatch_data.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


def test_preserves_actual_source_geometry_and_marks_exercise(tmp_path):
    destination=tmp_path/'演练'
    summary=module.prepare(ROOT,destination)
    assert summary['roads']>0 and summary['buildings']>0
    assert summary['native_network_created'] is False
    original=json.loads((ROOT/'data/spacenet8/sample/Germany_Training_Public/annotations/0_41_59.geojson').read_text())
    roads=json.loads((destination/'roads.geojson').read_text(encoding='utf-8'))['features']
    for road in roads:
        index=int(road['id'].split(':')[-1])
        assert road['geometry']==original['features'][index]['geometry']
    resources=json.loads((destination/'resources.json').read_text(encoding='utf-8'))
    assert resources['scenario_only']
    for resource in resources['resources']:
        assert resource['scenario_only'] and not resource['is_real_asset']
        assert 'node' not in resource  # Never invent a MapGIS node ID.


def test_refuses_overwrite_and_path_traversal(tmp_path):
    with pytest.raises(FileExistsError): module.prepare(ROOT,tmp_path)
    with pytest.raises(ValueError): module.prepare(ROOT,tmp_path/'out','../bad.geojson')


def test_endpoint_staging_is_explicit_and_keeps_real_roads(tmp_path):
    output=tmp_path/'endpoint'
    module.prepare(ROOT,output,endpoint_staging=True)
    resources=json.loads((output/'resources.json').read_text(encoding='utf-8'))['resources']
    roads=json.loads((output/'roads.geojson').read_text(encoding='utf-8'))['features']
    for resource in resources:
        road=next(r for r in roads if r['id']==resource['source_road_id'])
        assert resource['source_vertex_index']==0
        assert [resource['longitude'],resource['latitude']]==road['geometry']['coordinates'][0]
        assert resource['location_kind']=='fictional_shared_endpoint_staging'
        assert resource['is_real_asset'] is False
    scenario=json.loads((output/'scenario.json').read_text(encoding='utf-8'))
    assert scenario['destination']['source_vertex_index']>0
    assert 'node_to_node_only' in scenario['scope']
