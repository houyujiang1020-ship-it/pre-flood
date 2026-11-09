"""Run the real trained checkpoint through the AI API in an isolated process, without replacing the live service."""
import argparse
import json
import os
import sys
import time
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--pre',type=Path,required=True)
    parser.add_argument('--post',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    os.environ['FLOODGUARD_CONFIG']=str(args.config.resolve(strict=True))
    sys.path.insert(0,str(root/'app/ai-service'))
    from fastapi.testclient import TestClient
    from PIL import Image
    from app.main import app
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    with TestClient(app) as client:
        health=client.get('/health'); health.raise_for_status()
        assert health.json()['device']=='cuda'
        info=client.get('/model/info'); info.raise_for_status()
        submitted=client.post('/inference/flood',json={'pre_image_path':str(args.pre.resolve(strict=True)),
                'post_image_path':str(args.post.resolve(strict=True)),'output_dir':str(output)})
        submitted.raise_for_status()
        job_id=submitted.json()['job_id']
        deadline=time.monotonic()+120
        while True:
            response=client.get('/jobs/'+job_id); response.raise_for_status()
            job=response.json()
            if job['status'] in ('completed','failed'):
                break
            if time.monotonic()>deadline:
                raise TimeoutError('Real model job did not finish')
            time.sleep(.1)
        if job['status']!='completed':
            raise RuntimeError(job)
        result=job['result']
        assert result['model_version']==info.json()['version']
        assert result['model_version'].startswith('research-sha256-')
        with Image.open(args.pre) as reference:
            size=reference.size
        for path in result['class_masks'].values():
            with Image.open(path) as image:
                assert image.size==size
                assert set(image.getdata()) <= {0,255}
        report={'health':health.json(),'model':info.json(),'job':job,'inference_verified':True,
                'accuracy_verified':False,'scope':'Real CUDA API inference; NOT MapGIS or production accuracy acceptance'}
        (output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))


if __name__=='__main__':
    main()
