"""Freeze an expanded research split and report actual class coverage before training."""
import csv
import argparse
import json
from pathlib import Path
from train_smoke import load_pair
from train_full import CLASSES


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stratified',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    area_name='Germany_Training_Public'
    area=root/'data/spacenet8/sample'/area_name
    with (area/f'{area_name}_label_image_mapping.csv').open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))[:18]
    # Preserve original validation/test tiles. New tiles are assigned by table order,
    # before inspecting model predictions, never selected on favorable accuracy.
    partitions={'train':rows[:4]+rows[6:12], 'validation':[rows[4]]+rows[12:15], 'test':[rows[5]]+rows[15:18]}
    suffix='-stratified' if args.stratified else ''
    if args.stratified:
        # Pre-training label audit found no flooded buildings in the initial validation split.
        # Swap a newly downloaded labeled tile with a validation tile, never touching test.
        partitions['train']=rows[:4]+rows[6:11]+[rows[14]]
        partitions['validation']=[rows[4]]+rows[12:14]+[rows[11]]
    coverage={}
    for name,split in partitions.items():
        counts=[0]*4
        for row in split:
            labels=load_pair(area,row,256)[2]
            counts=[v+int(labels[i].sum()) for i,v in enumerate(counts)]
        coverage[name]=dict(zip(CLASSES,counts))
    if args.stratified and any(v==0 for counts in coverage.values() for v in counts.values()):
        raise ValueError('All splits must cover all classes in this stratified research run')
    config={'data_root':'data/spacenet8/sample','output_dir':'models/checkpoints/spacenet8-balanced18'+suffix,
            'image_size':256,'epochs':40,'learning_rate':0.0003,'seed':42,'device':'cuda',
            'balanced_loss':True,'dice_weight':0.5,
            'test_scope':'Small held-out tiles in same Germany region, not independent-region or official competition test. No production claim.',
            'splits':{name:[{'area':area_name,'label':row['label']} for row in split] for name,split in partitions.items()}}
    target=root/f'config/training.balanced18{suffix}.json'
    with target.open('x',encoding='utf-8') as stream:
        json.dump(config,stream,indent=2)
    with (root/f'models/checkpoints/balanced18{suffix}-coverage.json').open('x',encoding='utf-8') as stream:
        json.dump(coverage,stream,indent=2)
    print(json.dumps(coverage,indent=2))


if __name__=='__main__':
    main()
