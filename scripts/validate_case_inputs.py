"""Static case preflight. It never claims MapGIS host or license verification."""
import argparse
import hashlib
import json
from pathlib import Path

import rasterio
from pyproj import CRS
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
DEMO_FILES = {
    'prediction': '01_flood_prediction.json', 'buildings': '02_buildings.geojson',
    'roads': '03_roads.geojson', 'population_csv': '04_population.csv',
    'resources': '05_resources.json', 'flood_extent': '07_flood_extent.geojson',
    'population_grid': '08_population_grid.geojson', 'administrative': '09_admin_area.geojson',
    'pre_image': 'pre.tif', 'post_image': 'post.tif',
}
GEOMETRIES = {'buildings': 'Polygon', 'roads': 'LineString',
              'flood_extent': 'Polygon', 'population_grid': 'Polygon', 'administrative': 'Polygon'}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _crs(value):
    result = CRS.from_user_input(value)
    if not result.is_projected or not all(axis.unit_name.lower() in ('metre', 'meter') for axis in result.axis_info[:2]):
        raise ValueError('projected metre CRS required')
    return result


def audit(manifest: Path) -> dict:
    manifest = manifest.resolve()
    root = json.loads(manifest.read_text(encoding='utf-8'))
    demo = 'simulation_only' in root
    source = root.get('sources', {})
    files = {}
    issues = []
    if demo:
        selected = root.get('input_files', {})
        if not isinstance(selected, dict):
            raise ValueError('input_files must be an object')
        paths = {key: manifest.parent / selected.get(key, name) for key, name in DEMO_FILES.items()}
    else:
        paths = {key: manifest.parent / entry.get('path', '') for key, entry in source.items() if isinstance(entry, dict)}
        for key in ('pre_image', 'post_image', 'prediction', 'buildings', 'roads',
                    'population', 'flood_extent', 'resources', 'road_status'):
            if key not in paths:
                issues.append(f'missing source: {key}')
    crs_values = {}
    bounds = {}
    reference_objects = {}
    prediction_objects = {}
    reviewed_roads = {}
    for key, path in paths.items():
        entry = {'path': str(path.resolve()), 'exists': path.is_file()}
        files[key] = entry
        if not path.is_file() or path.stat().st_size == 0:
            issues.append(f'missing/empty file: {key}')
            continue
        entry['sha256'] = digest(path)
        if not demo:
            details = source[key]
            for field in ('sha256', 'provenance', 'license', 'source_date'):
                if not details.get(field):
                    issues.append(f'{key}: missing {field}')
            if details.get('sha256', '').lower() != entry['sha256']:
                issues.append(f'{key}: sha256 mismatch')
        try:
            if path.suffix.lower() in ('.tif', '.tiff'):
                with rasterio.open(path) as dataset:
                    if dataset.crs is None or dataset.transform.is_identity:
                        raise ValueError('missing CRS or affine transform')
                    entry.update(width=dataset.width, height=dataset.height,
                                 affine=list(dataset.transform)[:6], crs=dataset.crs.to_string())
                    crs_values[key] = _crs(dataset.crs)
                    bounds[key] = dataset.bounds
            elif path.suffix.lower() == '.geojson':
                data = json.loads(path.read_text(encoding='utf-8'))
                declared = data.get('crs', {}).get('properties', {}).get('name')
                if not declared:
                    raise ValueError('missing declared CRS')
                crs_values[key] = _crs(declared)
                features = data.get('features')
                if data.get('type') != 'FeatureCollection' or not isinstance(features, list):
                    raise ValueError('invalid FeatureCollection')
                ids = set()
                for feature in features:
                    geometry = feature.get('geometry') or {}
                    if key in GEOMETRIES and geometry.get('type') != GEOMETRIES[key]:
                        raise ValueError(f'wrong geometry type: {geometry.get("type")}')
                    obj = shape(geometry)
                    if obj.is_empty or not obj.is_valid:
                        raise ValueError('invalid/empty geometry')
                    object_id = feature.get('id') or feature.get('properties', {}).get('object_id') or feature.get('properties', {}).get('id')
                    if key in ('buildings', 'roads', 'population_grid', 'population', 'administrative'):
                        if not object_id or object_id in ids:
                            raise ValueError('missing/duplicate stable object ID')
                        ids.add(object_id)
                    if key in ('buildings', 'roads'):
                        reference_objects[object_id] = (key, obj)
                    props = feature.get('properties', {})
                    if key == 'administrative':
                        if not props.get('area_id'):
                            raise ValueError('area_id missing')
                        risk = props.get('resource_distance_risk')
                        if not isinstance(risk, (int, float)) or not 0 <= risk <= 1:
                            raise ValueError('invalid resource_distance_risk')
                        if not props.get('resource_risk_source') or not props.get('resource_risk_method'):
                            issues.append('administrative: resource distance source/method missing')
                    if key in ('population_grid', 'population'):
                        if not props.get('grid_id'):
                            raise ValueError('grid_id missing')
                        if not isinstance(props.get('population'), (int, float)) or props['population'] < 0:
                            raise ValueError('invalid population field')
                        if props.get('population_unit') != 'persons_per_cell' or not props.get('population_source'):
                            issues.append(f'{key}: population unit/source missing for {object_id}')
                    if key == 'flood_extent' and (props.get('flood_kind') != 'CONTINUOUS_EXTENT' or not props.get('flood_source')):
                        issues.append('flood_extent: independent continuous flood source/kind missing')
                entry.update(crs=declared, feature_count=len(features))
            elif path.suffix.lower() == '.json':
                data = json.loads(path.read_text(encoding='utf-8'))
                if key in ('prediction', 'flood'):
                    objects = data.get('objects')
                    if not isinstance(objects, list) or not objects:
                        raise ValueError('missing prediction objects')
                    crs_values[key] = _crs(data.get('crs_wkt'))
                    ids = [item.get('object_id') for item in objects]
                    if any(not value for value in ids) or len(set(ids)) != len(ids):
                        raise ValueError('missing/duplicate prediction object ID')
                    entry['object_count'] = len(objects)
                    prediction_objects = {item['object_id']: item for item in objects}
                elif key == 'resources':
                    if demo:
                        resources = data.get('resources')
                        if not isinstance(resources, list) or not resources or any(not r.get('id') or not r.get('kind') for r in resources):
                            raise ValueError('resource ID/kind missing')
                        issues.append('resources: source inventory is not a native MapGIS resource manifest')
                    elif data.get('engine') != 'MapGIS' or not isinstance(data.get('layer_urls'), dict) or any(not str(data['layer_urls'].get(kind, '')).startswith('gdbp://') for kind in ('VEHICLE', 'MEDICAL', 'SHELTER')):
                        raise ValueError('missing MapGIS resource layer bindings')
                elif key == 'road_status':
                    if not data.get('network_url') or not data.get('roads_url') or not isinstance(data.get('network_edge_count'), int) or data['network_edge_count'] <= 0 or data.get('unlisted_status') != 'NORMAL' or not data.get('unlisted_evidence') or not isinstance(data.get('roads'), list):
                        raise ValueError('road status lacks network/source mapping or review evidence')
                    for review in data['roads']:
                        if not review.get('source_feature_id') or not review.get('evidence') or review.get('status') not in ('NORMAL', 'FLOODED', 'HIGH_RISK', 'BLOCKED'):
                            raise ValueError('road status entry is invalid')
                        if review['source_feature_id'] in reviewed_roads:
                            raise ValueError('duplicate road status ID')
                        reviewed_roads[review['source_feature_id']] = review['status']
        except (ValueError, KeyError, TypeError, rasterio.errors.RasterioError) as error:
            issues.append(f'{key}: {error}')
    if 'pre_image' in files and 'post_image' in files and files['pre_image'].get('affine') and files['post_image'].get('affine'):
        if files['pre_image']['affine'] != files['post_image']['affine'] or (files['pre_image'].get('width'), files['pre_image'].get('height')) != (files['post_image'].get('width'), files['post_image'].get('height')) or files['pre_image'].get('crs') != files['post_image'].get('crs'):
            issues.append('pre/post image grids differ')
    if crs_values and any(not next(iter(crs_values.values())).equals(value, ignore_axis_order=True)
                          for value in crs_values.values()):
        issues.append('case inputs use different CRS')
    if prediction_objects and reference_objects:
        if set(prediction_objects) != set(reference_objects):
            issues.append('prediction and reference object IDs differ')
        else:
            for object_id, prediction in prediction_objects.items():
                expected_type = 'building' if reference_objects[object_id][0] == 'buildings' else 'road'
                try:
                    geometry_matches = shape(prediction.get('geometry')).equals(reference_objects[object_id][1])
                except (ValueError, TypeError, KeyError):
                    geometry_matches = False
                if prediction.get('type') != expected_type or not geometry_matches:
                    issues.append(f'prediction/reference geometry or type mismatch: {object_id}')
    if any(item.get('type') == 'road' and item.get('flood_status') == 'blocked' for item in prediction_objects.values()) and not paths.get('road_status'):
        issues.append('blocked road has no independent road_status ledger')
    if 'road_status' in paths and paths['road_status'].is_file() and prediction_objects:
        predicted_blocked = {key for key, item in prediction_objects.items()
                             if item.get('type') == 'road' and item.get('flood_status') == 'blocked'}
        ledger_blocked = {key for key, status in reviewed_roads.items() if status == 'BLOCKED'}
        if predicted_blocked != ledger_blocked:
            issues.append('blocked road IDs differ from independent road_status ledger')
    scenario = root.get('scenario')
    if not isinstance(scenario, dict):
        issues.append('missing native MapGIS scenario and road/resource bindings' if demo else 'missing scenario')
    else:
        for key in ('administrativeUrl', 'populationUrl', 'floodExtentUrl', 'networkUrl', 'sourceRoadsUrl'):
            if not str(scenario.get(key, '')).startswith('gdbp://'):
                issues.append(f'missing/invalid MapGIS URL: {key}')
        for key in ('preImage', 'postImage', 'predictionJson', 'resourceManifest', 'roadStatusLedger',
                    'startResourceId', 'targetResourceId', 'areaNameField', 'resourceRiskField'):
            if not scenario.get(key):
                issues.append(f'missing scenario field: {key}')
        if scenario.get('simulated') is not demo:
            issues.append('simulation/formal mode mismatch')
        if scenario.get('aiMode') != 'REPLAY':
            issues.append('only REPLAY can pass current object-case preflight')
        if not demo and 'road_status' in paths and paths['road_status'].is_file():
            road = json.loads(paths['road_status'].read_text(encoding='utf-8'))
            if road.get('network_url') != scenario.get('networkUrl') or road.get('roads_url') != scenario.get('sourceRoadsUrl'):
                issues.append('road status network/source URL differs from scenario')
    source_issue = any(issue.startswith(('missing source:', 'missing/empty file:')) or
                       any(term in issue for term in ('sha256 mismatch', 'missing sha256', 'missing provenance',
                                                      'missing license', 'missing source_date', 'invalid FeatureCollection',
                                                      'missing prediction objects', 'resource ID/kind missing',
                                                      'missing MapGIS resource', 'road status lacks', 'road status entry is invalid'))
                       for issue in issues)
    return {'schema_version': 1, 'manifest': str(manifest), 'mode': 'REPLAY_SIMULATION' if demo else 'FORMAL',
            'files_valid': bool(files) and all(item['exists'] for item in files.values()) and not source_issue,
            'spatial_valid': bool(crs_values) and not any(any(term in issue for term in ('CRS', 'affine', 'grid', 'geometry', 'object IDs', 'projected metre', 'population unit/source', 'continuous flood source/kind', 'stable object ID')) for issue in issues),
            'data_complete': not issues, 'host_verified': False, 'scenario_ready': False,
            'declared_ready': root.get('ready', False), 'files': files, 'issues': issues,
            'note': 'Static preflight only; gdbp accessibility, MapControl and license require official MapGIS host.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.manifest)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0 if result['data_complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
