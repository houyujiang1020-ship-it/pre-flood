"""Package a clearly labeled development handoff, excluding proprietary SDKs and secrets."""
import datetime
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    plugin = ROOT / 'app/mapgis-flood-desktop/target/mapgis-floodguard-plugin.jar'
    checkpoint = ROOT / 'models/checkpoints/spacenet8-smoke/smoke_model.pth'
    if not plugin.is_file() or not checkpoint.is_file():
        raise FileNotFoundError('Build plugin and train smoke model before packaging')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out = ROOT / 'release' / f'MapGIS-FloodGuard-development-{stamp}'
    out.mkdir(parents=True, exist_ok=False)
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache', 'target', 'application.local.yaml')
    for folder in ('app', 'scripts', 'config', 'docs', 'tests'):
        shutil.copytree(ROOT / folder, out / folder, ignore=ignore)
    for folder in ('data/demo', 'data/spacenet8/sample', 'models/checkpoints/spacenet8-smoke'):
        shutil.copytree(ROOT / folder, out / folder)
    provenance = json.loads((ROOT / 'data/spacenet8/sample-manifest.json').read_text(encoding='utf-8'))
    for item in provenance['objects']:
        item['path'] = Path(item['path']).relative_to(ROOT).as_posix()
    (out / 'data/spacenet8/sample-manifest.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    plugin_out = out / plugin.relative_to(ROOT)
    plugin_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plugin, plugin_out)
    # Only the audited pure-image architecture and upstream attribution are needed at runtime.
    upstream_files = ['baseline/models/other/siamunetdif.py', 'LICENSE', 'README.md']
    for relative in upstream_files:
        source = ROOT / 'upstream/SpaceNet8' / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = out / 'upstream/SpaceNet8' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    for name in ('README.md', 'README_CN.md', 'PROJECT_STATUS.md', 'BLOCKERS.md', 'NEXT_TASK.md'):
        shutil.copy2(ROOT / name, out / name)
    (out / 'VERSION.txt').write_text('0.2.0-development\nNOT COMPETITION-READY\nMapGIS runtime authorization and GIS E2E pending.\nSmoke checkpoint only; no validated accuracy.\n', encoding='utf-8')
    files = []
    for file in sorted(out.rglob('*')):
        if file.is_file():
            digest = hashlib.sha256()
            with file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            files.append({'path': file.relative_to(out).as_posix(), 'bytes': file.stat().st_size, 'sha256': digest.hexdigest()})
    (out / 'MANIFEST.json').write_text(json.dumps({'competition_ready': False, 'files': files}, indent=2), encoding='utf-8')
    archive = shutil.make_archive(str(out), 'zip', root_dir=out.parent, base_dir=out.name)
    print(json.dumps({'directory': str(out), 'archive': archive, 'files': len(files), 'competition_ready': False}, ensure_ascii=True))


if __name__ == '__main__':
    main()
