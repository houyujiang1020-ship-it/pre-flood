import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / 'experiments/diagnostics/visibility/germany-20260912-v2'
POSTS = {'post-event image 1': 'post1', 'post-event image 2': 'post2'}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


class Manifest:
    def __init__(self, path=DEFAULT / 'visibility_manifest.json', root=ROOT):
        self.path, self.root = Path(path).resolve(), Path(root).resolve()
        self.sha256 = digest(self.path)
        self.samples, self.issues, self.keys = {}, [], {}
        entries = read_json(self.path)['entries']
        self.total_entries = len(entries)
        for entry in entries:
            sid = 'Germany_' + Path(entry['label']).stem
            if sid in self.samples:
                self.issues.append({'code': 'DUPLICATE_SAMPLE_ID', 'sample_id': sid})
                continue
            images = {'pre': entry['pre'], 'post1': None, 'post2': None}
            for post in entry['post_candidates']:
                slot = POSTS.get(post['column'])
                if not slot or images.get(slot):
                    self.issues.append({'code': 'INVALID_POST_COLUMN', 'sample_id': sid})
                    continue
                images[slot] = post
            # Resolve the actual mapping next to the manifest's PRE source, not a guessed data root.
            area = self.resolve(images['pre']['path']).parent.parent
            mapping = area / (entry['area'] + '_label_image_mapping.csv')
            label_path = area / 'annotations' / entry['label']
            try:
                with mapping.open(encoding='utf-8-sig', newline='') as f:
                    matches = [r for r in csv.DictReader(f) if r['label'] == entry['label']]
                if len(matches) != 1:
                    raise ValueError('label must have exactly one mapping row')
                for slot, column in [('pre', 'pre-event image'), ('post1', 'post-event image 1'), ('post2', 'post-event image 2')]:
                    actual = self.resolve(images[slot]['path']).name if images[slot] else ''
                    if actual != matches[0].get(column, '').strip():
                        raise ValueError('mapping disagrees with ' + slot)
            except Exception as exc:
                self.issues.append({'code': 'MAPPING_ERROR', 'sample_id': sid, 'detail': str(exc)})
            self.samples[sid] = {'sample_id': sid, 'split': entry['split'], 'label': str(label_path),
                                 'images': images, 'risk': max((p.get('review_priority_score', 0) for p in entry['post_candidates']), default=0)}
            self.keys[(entry['split'], entry['label'])] = sid

    def resolve(self, path):
        return (self.root / Path(path.replace('\\', '/'))).resolve()

    def source(self, sid):
        s = self.samples[sid]
        result = {'label': s['label']}
        for slot, image in s['images'].items():
            result[slot] = str(self.resolve(image['path'])) if image else None
            result[slot + '_sha256'] = image.get('sha256') if image else None
        return result
