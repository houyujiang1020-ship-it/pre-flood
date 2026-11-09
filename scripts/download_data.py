"""Download official SpaceNet8 objects without a GIS library or AWS account."""
import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import shutil
import time
import urllib.request
from pathlib import Path

BASE = 'https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/'
AREAS = ['Germany_Training_Public', 'Louisiana-East_Training_Public', 'Louisiana-West_Test_Public']


def _download_range(url: str, path: Path, start: int, end: int) -> None:
    expected = end - start + 1
    failures = 0
    while True:
        existing = path.stat().st_size if path.exists() else 0
        if existing > expected:
            raise RuntimeError(f'Oversized range file: {path}')
        if existing == expected:
            return
        request_start = start + existing
        request = urllib.request.Request(url, headers={'Range': f'bytes={request_start}-{end}'})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if getattr(response, 'status', None) != 206:
                    raise RuntimeError('Server does not support safe ranged download')
                content_range = response.headers.get('Content-Range', '')
                if not content_range.startswith(f'bytes {request_start}-{end}/'):
                    raise RuntimeError('Unexpected Content-Range: ' + content_range)
                with path.open('ab') as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        if output.tell() + len(chunk) > expected:
                            raise RuntimeError('Server returned more data than requested')
                        output.write(chunk)
            if path.stat().st_size != expected:
                raise OSError('Incomplete ranged response')
        except (TimeoutError, ConnectionError, OSError) as error:
            failures += 1
            if failures >= 10:
                raise RuntimeError(f'Range download failed after {failures} retries: {path}') from error
            delay = min(30, 2 ** min(failures, 4))
            print(f'Connection interrupted for {path.name}; retrying in {delay}s.', flush=True)
            time.sleep(delay)


def _parallel_transfer(url: str, target: Path, size: int, workers: int = 8, etag=None) -> None:
    partial = target.with_suffix(target.suffix + '.part')
    prefix = partial.stat().st_size if partial.exists() else 0
    if prefix > size:
        raise RuntimeError('Existing partial file is larger than remote object')
    if prefix == size:
        partial.replace(target)
        return
    manifest = target.with_suffix(target.suffix + '.ranges.json')
    # Persist the range layout. Changing connection count must never reinterpret
    # already-downloaded bytes as a different offset in the remote object.
    identity = {'url': url, 'size': size, 'prefix': prefix, 'workers': workers, 'etag': etag}
    if manifest.exists():
        if json.loads(manifest.read_text(encoding='utf-8')) != identity:
            raise RuntimeError('Range layout/source changed; resume with the original worker count and unchanged prefix')
    else:
        if list(target.parent.glob(target.name + '.part.[0-9][0-9]')):
            raise RuntimeError('Legacy range files have no offset manifest; keep them for inspection instead of guessing their layout')
        with manifest.open('x', encoding='utf-8') as stream:
            json.dump(identity, stream)
    remaining = size - prefix
    count = min(workers, max(1, remaining // (8 * 1024 * 1024)))
    count = max(1, count)
    chunk_size = (remaining + count - 1) // count
    ranges = []
    for index in range(count):
        start = prefix + index * chunk_size
        end = min(size - 1, start + chunk_size - 1)
        if start <= end:
            ranges.append((target.with_suffix(target.suffix + f'.part.{index:02d}'), start, end))
    print(f'Parallel download: {len(ranges)} connections, resuming after {prefix} bytes.', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ranges)) as executor:
        futures = [executor.submit(_download_range, url, path, start, end)
                   for path, start, end in ranges]
        for future in concurrent.futures.as_completed(futures):
            future.result()
    assembled = target.with_suffix(target.suffix + '.assembling')
    # An interrupted merge cannot corrupt the reusable sequential prefix.
    with assembled.open('wb') as output:
        if prefix:
            with partial.open('rb') as stream:
                shutil.copyfileobj(stream, output, 1024 * 1024)
        for path, start, end in ranges:
            if path.stat().st_size != end - start + 1:
                raise RuntimeError('Range incomplete before merge: ' + str(path))
            with path.open('rb') as stream:
                shutil.copyfileobj(stream, output, 1024 * 1024)
    if assembled.stat().st_size != size:
        raise RuntimeError('Merged download size mismatch')
    assembled.replace(target)
    for path, _, _ in ranges:
        path.unlink()
    if partial.exists():
        partial.unlink()
    manifest.unlink()


def download(key: str, target: Path, workers: int = 8) -> dict:
    url = BASE + key
    with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=30) as response:
        size = int(response.headers['Content-Length'])
        etag = response.headers.get('ETag')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size != size:
        partial = target.with_suffix(target.suffix + '.part')
        existing = partial.stat().st_size if partial.exists() else 0
        if shutil.disk_usage(target.parent).free < max(0, size - existing) + size + 100_000_000:
            raise RuntimeError('Insufficient disk space for ' + key)
        _parallel_transfer(url, target, size, workers, etag)
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'url': url, 'path': str(target), 'bytes': size, 'sha256': digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['sample', 'full'], default='sample')
    parser.add_argument('--count', type=int, default=2)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--area', choices=AREAS[:2], action='append',
                        help='Labeled AOI to download; repeat for both. Defaults to Germany for sample mode and both labeled AOIs for full mode.')
    args = parser.parse_args()
    if args.count < 1:
        parser.error('--count must be positive')
    if not 1 <= args.workers <= 16:
        parser.error('--workers must be between 1 and 16')
    root = Path(__file__).resolve().parents[1] / 'data' / 'spacenet8'
    records = []
    selected_areas = args.area or ([AREAS[0]] if args.mode == 'sample' else AREAS[:2])
    if args.mode == 'full':
        for area in selected_areas:
            records.append(download('tarballs/' + area + '.tar.gz', root / 'archives' / (area + '.tar.gz'), args.workers))
    else:
        if len(selected_areas) != 1:
            parser.error('sample mode accepts exactly one --area')
        area = selected_areas[0]
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
    if args.mode == 'sample':
        target = root / f'sample-{area}-manifest.json'
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        # Preserve the historical Germany path used by release/provenance code.
        if area == AREAS[0]:
            (root / 'sample-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        (root / 'full-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Downloaded/verified {len(records)} official objects.')


if __name__ == '__main__':
    main()
