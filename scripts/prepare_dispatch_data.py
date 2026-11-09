"""Extract official source features verbatim and create explicitly fictional exercise inventory.

No reprojection, topology, spatial matching or routing is performed here: those belong to MapGIS.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def prepare(root: Path, destination: Path, label='0_41_59.geojson', endpoint_staging=False):
    if Path(label).name != label:
        raise ValueError('Label must be a filename')
    source=root/'data/spacenet8/sample/Germany_Training_Public/annotations'/label
    content=source.read_bytes()
    manifest_path=root/'data/spacenet8/sample-Germany_Training_Public-manifest.json'
    if not manifest_path.is_file(): manifest_path=root/'data/spacenet8/sample-manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    entry=next((e for e in manifest['objects'] if Path(e['path']).resolve()==source.resolve()),None)
    if entry is None or entry['sha256']!=hashlib.sha256(content).hexdigest():
        raise ValueError('Official source provenance/hash verification failed')
    original=json.loads(content)
    roads, buildings=[],[]
    for index,feature in enumerate(original['features']):
        properties=feature.get('properties',{})
        is_road=properties.get('highway') not in (None,'')
        is_building=properties.get('building') not in (None,'','no')
        if not is_road and not is_building:
            continue
        copied=copy.deepcopy(feature)
        identity=f'{Path(label).stem}:{index}'
        copied['id']=identity
        copied['properties']['fg_source_id']=identity
        copied['properties']['fg_source_label']=label
        (roads if is_road else buildings).append(copied)
    candidates=[r for r in roads if r['geometry']['type']=='LineString' and len(r['geometry']['coordinates'])>=3]
    if not candidates or not buildings:
        raise ValueError('Need a real line with at least three vertices and building labels')
    anchor=max(candidates,key=lambda f:len(f['geometry']['coordinates']))
    vertices=anchor['geometry']['coordinates']
    resources=[]
    staging_vertices=[0,0,0] if endpoint_staging else [0,len(vertices)//3,2*len(vertices)//3]
    for index,vertex_index in enumerate(staging_vertices,1):
        resources.append({'id':f'EXERCISE-VEHICLE-{index:02}', 'name':f'演练救援车辆{index}',
            'type':'rescue_vehicle','capacity':[5,8,10][index-1],'capacity_unit':'persons_per_trip',
            'scenario_only':True,'is_real_asset':False,
            'location_kind':'fictional_shared_endpoint_staging' if endpoint_staging else 'source_road_vertex_not_verified_station',
            'longitude':vertices[vertex_index][0],'latitude':vertices[vertex_index][1],
            'source_road_id':anchor['id'],'source_vertex_index':vertex_index})
    destination.mkdir(parents=True,exist_ok=False)
    def write(name,value):
        (destination/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    common={'type':'FeatureCollection','source_url':entry['url'],'source_sha256':entry['sha256'],
            'license':'CC-BY-SA-4.0','coordinate_order':'longitude,latitude','crs_name':'EPSG:4326'}
    write('roads.geojson',{**common,'features':roads})
    write('buildings.geojson',{**common,'features':buildings})
    write('resources.json',{'schema_version':1,'scenario_only':True,'warning':'虚构演练资源，非真实消防站、医院或车辆台账',
                            'resources':resources})
    write('resources.geojson',{'type':'FeatureCollection','scenario_only':True,'features':[
        {'type':'Feature','id':r['id'],'geometry':{'type':'Point','coordinates':[r['longitude'],r['latitude']]},
         'properties':r} for r in resources]})
    write('scenario.json',{'schema_version':1,'scenario_only':True,'network_ready':False,
        'warning':'仅为软件演练假设，非实际灾情/通行核查。MapGIS建网后才可绑定原生节点与边。',
        'resource_type':'rescue_vehicle','demand':12,'capacity_unit':'persons_per_trip',
        'resource_placement':'fictional_shared_road_start' if endpoint_staging else 'source_vertices',
        'scope':'node_to_node_only; not arbitrary roadside resource access' if endpoint_staging else 'source_vertex_binding',
        'destination':{'source_road_id':anchor['id'],'source_vertex_index':len(vertices)-1,
                       'longitude':vertices[-1][0],'latitude':vertices[-1][1]},
        'scenarios':[{'id':'baseline','closed_source_road_ids':[]},
                     {'id':'closure','closed_source_road_ids':[anchor['id']]}],
        'assumed_speed_kph':30,'speed_is_measured':False,
        'native_engine_required':'MapGIS','target_crs':'EPSG:32632',
        'source_label':label})
    write('manifest.json',{'schema_version':1,'source':entry,'roads':len(roads),'buildings':len(buildings),
        'resource_count':len(resources),'native_network_created':False,'scenario_only_resources':True,
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(destination.iterdir()) if p.is_file()}})
    return {'directory':str(destination.resolve()),'roads':len(roads),'buildings':len(buildings),'resources':len(resources),
            'native_network_created':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('data/demo/dispatch-spacenet8'))
    parser.add_argument('--label',default='0_41_59.geojson')
    parser.add_argument('--endpoint-staging',action='store_true',help='Create a distinct, fictional shared road-endpoint staging scenario')
    args=parser.parse_args()
    print(json.dumps(prepare(Path(__file__).resolve().parents[1],args.output,args.label,args.endpoint_staging),ensure_ascii=True))
