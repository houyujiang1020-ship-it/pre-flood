"""Download official SpaceNet8 objects without a GIS library or AWS account."""
import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

BASE = 'https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/'
AREAS = ['Germany_Training_Public', 'Louisiana-East_Training_Public', 'Louisiana-West_Test_Public']


def download(key: str, target: Path) -> dict:
    url = BASE + key
    with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=30) as response:
        size = int(response.headers['Content-Length'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size != size:
        partial = target.with_suffix(target.suffix + '.part')
        existing = partial.stat().st_size if partial.exists() else 0
        if shutil.disk_usage(target.parent).free < max(0, size - existing) + 100_000_000:
            raise RuntimeError('Insufficient disk space for ' + key)
        subprocess.run(['curl.exe', '--fail', '--location', '--retry', '3', '--connect-timeout', '30',
                        '--continue-at', '-', '--output', str(partial), url], check=True)
        if partial.stat().st_size != size:
            raise RuntimeError('Downloaded size mismatch: ' + key)
        partial.replace(target)
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'url': url, 'path': str(target), 'bytes': size, 'sha256': digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['sample', 'full'], default='sample')
    parser.add_argument('--count', type=int, default=2)
    args = parser.parse_args()
    if args.count < 1:
        parser.error('--count must be positive')
    root = Path(__file__).resolve().parents[1] / 'data' / 'spacenet8'
    records = []
    if args.mode == 'full':
        for area in AREAS:
            records.append(download('tarballs/' + area + '.tar.gz', root / 'archives' / (area + '.tar.gz')))
    else:
        area = AREAS[0]
        mapping = area + '_label_image_mapping.csv'
        mapping_path = root / 'sample' / area / mapping
        records.append(download(area + '/' + mapping, mapping_path))
        rows = list(csv.DictReader(io.StringIO(mapping_path.read_text(encoding='utf-8-sig'))))[:args.count]
        for row in rows:
            for column, folder in [('label', 'annotations'), ('pre-event image', 'PRE-event'),
                                   ('post-event image 1', 'POST-event')]:
                name = row[column].strip()
                if not name or Path(name).name != name:
                    raise ValueError('Invalid source object name')
                records.append(download(f'{area}/{folder}/{name}', root / 'sample' / area / folder / name))
    manifest = {'source': 'https://spacenet.ai/sn8-challenge/', 'license': 'CC-BY-SA-4.0',
                'mode': args.mode, 'objects': records}
    (root / f'{args.mode}-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Downloaded/verified {len(records)} official objects.')


if __name__ == '__main__':
    main()
