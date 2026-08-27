"""Explicit real-model API check; failure is never converted to a skipped test."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ['FLOODGUARD_CONFIG'] = str(ROOT / 'config/application.smoke.yaml')
sys.path.insert(0, str(ROOT / 'app/ai-service'))
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
health = client.get('/health')
assert health.status_code == 200, health.text
assert health.json()['backend'] == 'siamunet-smoke'
assert health.json()['device'] == 'cuda'
assert health.json()['production_checkpoint_loaded'] is False
sample = ROOT / 'models/checkpoints/spacenet8-smoke'
request = {'pre_image_path': str(sample / 'validation_pre.png'),
           'post_image_path': str(sample / 'validation_post.png'),
           'output_dir': str(ROOT / 'data/outputs/官方烟测')}
submitted = client.post('/inference/flood', json=request)
assert submitted.status_code == 202, submitted.text
job_id = submitted.json()['job_id']
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    job = client.get(f'/jobs/{job_id}').json()
    if job['status'] in ('completed', 'failed'):
        break
    time.sleep(0.05)
assert job['status'] == 'completed', job
result = job['result']
assert result['statistics']['backend'] == 'siamunet-smoke'
assert result['statistics']['production_ready'] is False
for path in result['class_masks'].values():
    assert Path(path).is_file(), path
assert Path(result['preview_path']).is_file()
print(json.dumps({'health': health.json(), 'job_id': job_id, 'statistics': result['statistics']}, indent=2))
