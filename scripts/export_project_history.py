"""Export retained project logs/evidence without modifying source files."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = set()
    for name in ('PROJECT_STATUS.md', 'NEXT_TASK.md', 'BLOCKERS.md', 'README_CN.md'):
        paths.add(ROOT / name)
    paths.update((ROOT / 'docs').rglob('*.md'))
    for directory in ('logs', 'runtime'):
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and (path.suffix in ('.log', '.txt') or path.name.startswith('competition-readiness') and path.suffix == '.json'):
                paths.add(path)
    evidence_names = {'network-build.json', 'dispatch-preparation.json', 'exercise-dispatch.json',
                      'spatial-result.json', 'native-acceptance.json', 'verification.json'}
    for directory in ('data/demo', 'data/outputs', 'outputs', 'runtime'):
        for path in (ROOT / directory).rglob('*.json'):
            if path.name in evidence_names:
                paths.add(path)
    for path in (ROOT / 'models/checkpoints').rglob('*.json'):
        if path.name in ('history.json', 'training_report.json', 'calibration.json', 'calibration.thresholds.json') or 'comparison' in path.name:
            paths.add(path)
    paths.update((ROOT / 'data/processed/full-audit-20260830').glob('audit.json'))
    app = ROOT / 'app/mapgis-flood-desktop'
    for parent in [app, ROOT / 'runtime']:
        for path in parent.rglob('*'):
            if path.is_file() and ((path.parent.name == 'surefire-reports' and path.suffix in ('.xml', '.txt')) or path.name.startswith('hs_err_pid') and path.suffix == '.log'):
                paths.add(path)
    paths.update(ROOT.glob('hs_err_pid*.log'))
    out = ROOT / 'outputs' / ('history-export-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    out.mkdir(parents=True, exist_ok=False)
    archive = out / '项目现存日志与证据.zip'
    records = []
    with ZipFile(archive, 'x', compression=ZIP_DEFLATED) as bundle:
        for path in sorted(paths):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            records.append({'path': relative, 'bytes': len(data),
                            'sha256': hashlib.sha256(data).hexdigest()})
            bundle.writestr(relative, data)
        manifest = {'scope': 'Retained project logs/evidence, not complete historical terminal replay',
                    'created_local': datetime.now().isoformat(),
                    'privacy': 'Local audit only; logs may contain paths/command lines. Review before external sharing.',
                    'files': records}
        encoded = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
        bundle.writestr('MANIFEST.json', encoded)
    with ZipFile(archive) as bundle:
        assert bundle.testzip() is None, 'ZIP CRC failed'
        for entry in records:
            assert hashlib.sha256(bundle.read(entry['path'])).hexdigest() == entry['sha256']
    (out / '日志清单.json').write_bytes(encoded)
    print(json.dumps({'archive': str(archive), 'manifest': str(out / '日志清单.json'),
                      'files': len(records), 'source_bytes': sum(r['bytes'] for r in records),
                      'zip_bytes': archive.stat().st_size, 'crc_and_sha256_verified': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
