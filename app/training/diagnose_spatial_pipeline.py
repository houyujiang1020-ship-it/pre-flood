"""CPU-only, reproducible spatial/label/cache audit; never changes training data."""
import csv
import hashlib
import json
from pathlib import Path
import random
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_bounds, transform_geom
from shapely.geometry import shape, box
from PIL import Image, ImageDraw
import torch
from train_smoke import load_pair, buffered_road, flooded_class
from train_full import pair_cache_key, CLASSES, split_rows

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'experiments/diagnostics'
COLORS = np.array([[255,220,40],[255,40,60],[40,220,255],[230,70,255]], dtype=np.uint8)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def summary(src):
    return dict(crs=str(src.crs), transform=list(src.transform), pixel_size=list(src.res),
                extent=list(src.bounds), width=src.width, height=src.height)


def main():
    torch.set_num_threads(1)
    for name in ['alignment','labels','reports','sampling']:
        (OUT/name).mkdir(parents=True,exist_ok=True)
    config_path=ROOT/'config/training.full-germany-20260830.json'
    config=json.loads(config_path.read_text())
    records=split_rows(config,ROOT)
    totals={}
    per_tile=[]
    for split,pairs in records.items():
        for i,(area,row) in enumerate(pairs):
            cache=ROOT/config['cache_dir']/(pair_cache_key(area,row,512)+'.pt')
            pre,post,y,v=torch.load(cache,map_location='cpu',weights_only=True)
            y=y.numpy()>0; v=v.numpy()>0; y=y & v[None]
            count=y.sum((1,2)).astype(int).tolist()
            item=dict(split=split,area=area.name,label=row['label'],cache=str(cache.relative_to(ROOT)),
                      valid_pixels=int(v.sum()),invalid_pixels=int((~v).sum()),
                      background_pixels=int((v & ~y.any(0)).sum()),
                      building_pixels=int((y[0]|y[1]).sum()),road_pixels=int((y[2]|y[3]).sum()),
                      flooded_building_pixels=count[1],flooded_road_pixels=count[3],
                      non_flooded_building_pixels=count[0],non_flooded_road_pixels=count[2],
                      has_flooded_building=count[1]>0,has_flooded_road=count[3]>0,
                      has_building=count[0]+count[1]>0,has_road=count[2]+count[3]>0,
                      background_only=sum(count)==0,
                      building_semantic_overlap_pixels=int((y[0]&y[1]).sum()),
                      road_semantic_overlap_pixels=int((y[2]&y[3]).sum()),
                      building_road_overlap_pixels=int(((y[0]|y[1])&(y[2]|y[3])).sum()))
            per_tile.append(item)
            if (i+1)%100==0: print(split,i+1,flush=True)
        items=[r for r in per_tile if r['split']==split]
        pixelkeys=[k for k in items[0] if k.endswith('_pixels')]
        totals[split]={'tiles':len(items),**{k:sum(r[k] for r in items) for k in pixelkeys},
                       **{k+'_patch_ratio':sum(r[k] for r in items)/len(items) for k in
                          ['has_flooded_building','has_flooded_road','has_building','has_road','background_only']}}
    save(OUT/'reports/class_distribution.json',dict(class_order=CLASSES,image_size=512,
         config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),totals=totals,tiles=per_tile,
         note='Background = valid pixels with no channel positive. Multilabel totals can overlap; Louisiana is reused research evaluation, not blind holdout.'))
    with (OUT/'reports/class_distribution.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=per_tile[0].keys());writer.writeheader();writer.writerows(per_tile)
    save(OUT/'sampling/tile_categories.json',{'train':[r for r in per_tile if r['split']=='train']})
    rng=random.Random(20260830)
    germany=records['train']+records['validation']
    selected=rng.sample(germany,20)+rng.sample(records['test'],20)
    alignment=[]; resolutions=[]
    for index,(area,row) in enumerate(selected):
        before,after,labels,valid=load_pair(area,row,512)
        cache=torch.load(ROOT/config['cache_dir']/(pair_cache_key(area,row,512)+'.pt'),map_location='cpu',weights_only=True)
        features=json.loads((area/'annotations'/row['label']).read_text())['features']
        with rasterio.open(area/'PRE-event'/row['pre-event image']) as pre, rasterio.open(area/'POST-event'/row['post-event image 1']) as post:
            post_bounds=transform_bounds(post.crs,pre.crs,*post.bounds)
            bounds=box(*pre.bounds); overlap=bounds.intersection(box(*post_bounds)).area/bounds.area
            grid=pre.transform*pre.transform.scale(pre.width/512,pre.height/512)
            label_geoms=[shape(transform_geom('EPSG:4326',pre.crs,f['geometry'])) for f in features if f.get('geometry')]
            item=dict(area=area.name,label=row['label'],pre=summary(pre),post=summary(post),
                      post_extent_in_pre_crs=list(post_bounds),extent_overlap_fraction=overlap,
                      raw_grid_identical=pre.crs==post.crs and pre.transform==post.transform and pre.shape==post.shape,
                      label_source_crs='EPSG:4326 GeoJSON (as interpreted by training)',
                      label_raster_crs=str(pre.crs),label_transform=list(grid),
                      labels_intersect_pre_extent=sum(g.intersects(bounds) for g in label_geoms),label_geometry_count=len(label_geoms),
                      valid_supervision_fraction=float(valid.mean()),cache_exact_match=all(torch.equal(a,b) for a,b in zip(cache,(before,after,labels,valid))))
            road_features=[f for f in features if f['properties'].get('highway') not in (None,'') and f['properties'].get('building') in (None,'no','')]
            item['road_utm_zones']=sorted(set((32600 if shape(f['geometry']).centroid.y>=0 else 32700)+min(60,int((shape(f['geometry']).centroid.x+180)//6)+1) for f in road_features))
            alignment.append(item)
            # First four random tiles per region, independent of resolution outcome.
            if index in list(range(4))+list(range(20,24)):
                native_shape=(pre.height,pre.width)
                mode_grids={'native_tile':(native_shape,pre.transform),
                            'resize512':((512,512),grid),
                            'higher1024':((1024,1024),pre.transform*pre.transform.scale(pre.width/1024,pre.height/1024))}
                modes={}; masks={}
                for mode,(dims,transform) in mode_grids.items():
                    all_mask=np.zeros(dims,dtype=np.uint8); vanished=0; flooded_vanished=0; flooded_total=0
                    for feature in road_features:
                        poly=buffered_road(feature['geometry'],pre.crs)
                        mask=rasterize([(poly,1)],out_shape=dims,transform=transform,all_touched=False,dtype='uint8')
                        all_mask|=mask
                        flood=flooded_class(feature['properties'].get('flooded'))
                        flooded_total+=flood
                        if not mask.any(): vanished+=1;flooded_vanished+=flood
                    masks[mode]=all_mask
                    modes[mode]=dict(shape=list(dims),road_pixels=int(all_mask.sum()),
                                    road_area_grid_units=float(all_mask.sum()*abs(transform.a*transform.e-transform.b*transform.d)),
                                    road_features=len(road_features),vanished_features=vanished,
                                    flooded_road_features=flooded_total,vanished_flooded_features=flooded_vanished)
                native=masks['native_tile']>0
                for mode in ['resize512','higher1024']:
                    restored=np.array(Image.fromarray(masks[mode]).resize((pre.width,pre.height),Image.Resampling.NEAREST))>0
                    modes[mode]['native_road_recall']=float((restored&native).sum()/max(1,native.sum()))
                    modes[mode]['native_road_iou']=float((restored&native).sum()/max(1,(restored|native).sum()))
                    modes[mode]['area_ratio_to_native']=modes[mode]['road_area_grid_units']/max(1e-20,modes['native_tile']['road_area_grid_units'])
                # Non-overlapping 512 windows cover native pixels exactly; no interpolated labels.
                tile_pixels=sum(int(native[y:y+512,x:x+512].sum()) for y in range(0,pre.height,512) for x in range(0,pre.width,512))
                modes['native_tile']['sliding_512_reassembled_road_pixels']=tile_pixels
                modes['native_tile']['sliding_512_preserves_all_pixels']=tile_pixels==int(native.sum())
                resolutions.append(dict(area=area.name,label=row['label'],modes=modes))
            if index in list(range(3))+list(range(20,23)):
                rgb=(before.numpy().transpose(1,2,0)*255).clip(0,255).astype('uint8')
                post_rgb=(after.numpy().transpose(1,2,0)*255).clip(0,255).astype('uint8')
                y=labels.numpy()>0; color=np.zeros_like(rgb)
                for channel in range(4): color[y[channel]]=COLORS[channel]
                overlay=rgb.copy(); positive=y.any(0)
                overlay[positive]=(rgb[positive]*.45+color[positive]*.55).astype('uint8')
                sheet=Image.new('RGB',(1024,1060),'white')
                for n,im in enumerate([rgb,post_rgb,color,overlay]):sheet.paste(Image.fromarray(im),((n%2)*512,36+(n//2)*512))
                ImageDraw.Draw(sheet).text((8,6),area.name+' '+row['label']+' | pre, post / GT, pre+GT',fill='black')
                name=area.name+'_'+Path(row['label']).stem+'.png'
                sheet.save(OUT/'alignment'/name)
                item['visualization']=str((OUT/'alignment'/name).relative_to(ROOT))
        print('alignment',index+1,row['label'],flush=True)
    save(OUT/'alignment/alignment_report.json',dict(seed=20260830,samples=alignment,
         checks={'all_cache_reproduced_exactly':all(r['cache_exact_match'] for r in alignment),
                 'min_extent_overlap':min(r['extent_overlap_fraction'] for r in alignment),
                 'min_valid_fraction':min(r['valid_supervision_fraction'] for r in alignment)},
         scope='Georeferencing and preprocessing consistency only. Same grid does not establish image-feature registration; visual review is separate.'))
    save(OUT/'reports/resolution_experiment.json',dict(seed=20260830,samples=resolutions,
         note='8 predetermined random tiles (4 per region); labels re-rasterized from vectors, matching actual pipeline, not resized masks. Area uses common CRS-grid units only for within-tile ratios, not physical area. Native tiling preserves labels by construction; this is not a trained-model accuracy comparison.'))
    print(json.dumps(totals),flush=True)


if __name__=='__main__':main()
