"""Compare old/new research checkpoints on the same held-out grid; never selects a checkpoint."""
import hashlib
import argparse
import importlib.util
import json
from pathlib import Path
import torch
from train_full import evaluate, split_rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default='config/training.balanced18-stratified.json')
    parser.add_argument('--output',default='models/checkpoints/balanced18-comparison.json')
    parser.add_argument('--scope',default='Exploratory comparison; not production certification')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    config=json.loads((root/args.config).read_text(encoding='utf-8'))
    records=split_rows(config,root)['test']
    source=root/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    spec=importlib.util.spec_from_file_location('official',source)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    results={}
    for label,relative,size in [('old_smoke','spacenet8-smoke/smoke_model.pth',128),
                                ('balanced18','spacenet8-balanced18-stratified/best_model.pth',256)]:
        path=root/'models/checkpoints'/relative
        model=module.SiamUnet_diff(num_classes=4,num_channels=3).cuda()
        model.load_state_dict(torch.load(path,map_location='cuda',weights_only=True)['state_dict'])
        class GridAdapter(torch.nn.Module):
            def __init__(self,network,input_size):
                super().__init__(); self.network=network; self.input_size=input_size
            def forward(self,pre,post):
                target=pre.shape[-2:]
                resize=lambda x: torch.nn.functional.interpolate(x,size=(self.input_size,self.input_size),mode='bilinear',align_corners=False)
                logits=self.network(resize(pre),resize(post))
                return torch.nn.functional.interpolate(logits,size=target,mode='nearest')
        results[label]={'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'input_size':size,'evaluation':evaluate(GridAdapter(model,size),records,256,'cuda')}
    report={'scope':args.scope,'test_labels':config['splits']['test'],
            'independent_region_test':all(x['area']=='Louisiana-East_Training_Public' for x in config['splits']['test']),
            'accuracy_acceptance_passed':False,'production_ready':False,'results':results}
    path=root/args.output; path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2)
    print(json.dumps(report))


if __name__=='__main__': main()
