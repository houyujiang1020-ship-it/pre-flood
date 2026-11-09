import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import rasterio
from rasterio.transform import from_origin
from PIL import Image
from fastapi.testclient import TestClient
from .manifest import Manifest, DEFAULT, ROOT, digest
from .review_store import Store, FLAGS, atomic_json
from .preview import Previews
from .validation import integrity, report
from .app import create_app


def fixture(root, count=3):
    area = root / '原始数据/Germany_Training_Public'
    for folder in ['PRE-event', 'POST-event', 'annotations']:
        (area / folder).mkdir(parents=True)
    entries, rows = [], []
    for i in range(count):
        images = {}
        for slot in ['pre', 'post1', 'post2'][:3 if i == 0 else 2]:
            path = area / ('PRE-event' if slot == 'pre' else 'POST-event') / f'{slot}{i}.tif'
            with rasterio.open(path, 'w', driver='GTiff', width=64, height=32, count=3, dtype='uint8',
                               crs='EPSG:4326', transform=from_origin(6, 51, .001, .001)) as f:
                f.write(np.full((3, 32, 64), {'pre': 50, 'post1': 100, 'post2': 150}[slot], dtype='uint8'))
            images[slot] = {'path': str(path.relative_to(root)), 'sha256': digest(path), 'review_priority_score': i / 10}
        label = f'0_{i}.geojson'
        atomic_json(area / 'annotations' / label, {'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': {'building': 'yes', 'flooded': 'yes'}, 'geometry': {
                'type': 'Polygon', 'coordinates': [[[6.01, 50.99], [6.02, 50.99], [6.02, 50.98], [6.01, 50.98], [6.01, 50.99]]]}},
            {'type': 'Feature', 'properties': {'highway': 'road', 'flooded': None}, 'geometry': {
                'type': 'LineString', 'coordinates': [[6.0, 50.985], [6.06, 50.985]]}}]})
        entries.append({'area': area.name, 'split': 'train', 'label': label, 'pre': images['pre'],
                        'post_candidates': [images[k] | {'column': 'post-event image ' + k[-1]} for k in ['post1', 'post2'] if k in images]})
        rows.append({'label': label, 'pre-event image': f'pre{i}.tif', 'post-event image 1': f'post1{i}.tif',
                     'post-event image 2': f'post2{i}.tif' if i == 0 else ''})
    with (area / (area.name + '_label_image_mapping.csv')).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    path = root / '清单/visibility_manifest.json'
    atomic_json(path, {'entries': entries})
    return Manifest(path, root)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='审查测试-')
        self.root = Path(self.temp.name)
        self.m = fixture(self.root)
        self.store = Store(self.m, self.root / '审查库')
        self.sid = 'Germany_0_0'

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, sid=None, **values):
        sid = sid or self.sid
        r = self.store.states[sid]
        return {'revision': r['revision'], 'decision': 'accepted', 'selected_post': 'post1',
                'flags': {k: False for k in FLAGS}, 'notes': '', 'reviewer': '测试审查人'} | values

    def test_manifest_chinese_paths(self):
        self.assertEqual(len(self.m.samples), 3)
        self.assertEqual(self.m.issues, [])
        self.assertEqual(self.store.resume(), self.sid)

    def test_missing_post2(self):
        sid = 'Germany_0_1'
        self.assertIsNone(self.m.samples[sid]['images']['post2'])
        self.assertFalse(Previews(self.m, self.root / 'previews').get(sid, 'post2')['available'])
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            self.store.save(sid, self.payload(sid, selected_post='post2'))

    def test_unknown_sample(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.store.save('bad', self.payload())

    def test_accepted_without_post(self):
        with self.assertRaisesRegex(ValueError, 'requires post'):
            self.store.save(self.sid, self.payload(selected_post=None))
        self.assertFalse(self.store.journal.exists())

    def test_reject_reason_required(self):
        with self.assertRaisesRegex(ValueError, 'reason'):
            self.store.save(self.sid, self.payload(decision='rejected', selected_post=None))
        self.store.save(self.sid, self.payload(decision='rejected', selected_post=None, notes='空间错位'))
        self.assertEqual(self.store.states[self.sid]['reject_reasons'], ['空间错位'])

    def test_reject_cannot_select_post(self):
        with self.assertRaisesRegex(ValueError, 'null'):
            self.store.save(self.sid, self.payload(decision='rejected', notes='cloud'))

    def test_save_reload_append_history(self):
        self.store.save(self.sid, self.payload())
        self.store.save(self.sid, self.payload(selected_post='post2'))
        fresh = Store(self.m, self.store.directory)
        self.assertEqual(fresh.states[self.sid]['selected_post'], 'post2')
        lines = [json.loads(l) for l in fresh.journal.read_text(encoding='utf-8').splitlines()]
        self.assertEqual([l['record']['selected_post'] for l in lines], ['post1', 'post2'])
        self.assertEqual(json.loads(fresh.snapshot.read_text(encoding='utf-8'))['sequence'], 2)

    def test_atomic_failure_recovers_wal(self):
        before = self.store.snapshot.read_bytes()
        with patch('tools.visibility_review.review_store.os.replace', side_effect=OSError('simulated power failure')):
            with self.assertRaises(OSError):
                self.store.save(self.sid, self.payload())
        self.assertEqual(self.store.snapshot.read_bytes(), before)
        fresh = Store(self.m, self.store.directory)
        self.assertEqual(fresh.states[self.sid]['decision'], 'accepted')
        self.assertTrue((fresh.directory / 'snapshot_recovery_report.json').exists())

    def test_corrupt_snapshot_recovery(self):
        self.store.save(self.sid, self.payload())
        self.store.snapshot.write_text('{bad', encoding='utf-8')
        fresh = Store(self.m, self.store.directory)
        self.assertEqual(fresh.summary()['accepted'], 1)

    def test_corrupt_journal_preserved(self):
        self.store.journal.write_bytes(b'{broken')
        with self.assertRaisesRegex(ValueError, 'Journal line'):
            Store(self.m, self.store.directory)
        self.assertEqual(self.store.journal.read_bytes(), b'{broken')

    def test_conflict(self):
        old = self.payload()
        self.store.save(self.sid, old)
        with self.assertRaises(RuntimeError):
            self.store.save(self.sid, old)

    def test_progress_filter_completion_resume(self):
        self.store.save(self.sid, self.payload(selected_post='post2'))
        self.assertEqual(self.store.query('post2'), [self.sid])
        self.assertEqual(self.store.query(search='0_1'), ['Germany_0_1'])
        self.assertEqual(self.store.query(risk=True)[0], 'Germany_0_2')
        self.assertEqual(self.store.summary()['pending'], 2)
        self.store.save('Germany_0_1', self.payload('Germany_0_1', decision='needs_review', selected_post=None))
        self.store.save('Germany_0_2', self.payload('Germany_0_2'))
        self.assertEqual(self.store.resume(), 'Germany_0_1')
        self.assertFalse(self.store.summary()['review_complete'])
        self.store.save('Germany_0_1', self.payload('Germany_0_1'))
        self.assertTrue(self.store.summary()['review_complete'])
        self.assertIsNone(self.store.resume())

    def test_backup_bounded(self):
        for i in range(220):
            self.store.save(self.sid, self.payload())
        self.assertEqual(len(list((self.store.directory / 'backups').glob('*.json'))), 10)

    def test_preview_dimensions_overlay_and_slots(self):
        p = Previews(self.m, self.root / 'previews')
        for slot, brightness in [('pre', 50), ('post1', 100), ('post2', 150)]:
            meta = p.get(self.sid, slot)
            folder = p.directory / self.sid / slot
            with Image.open(folder / 'rgb.png') as rgb:
                self.assertEqual(rgb.size, (64, 32))
            self.assertEqual(np.asarray(Image.open(folder / 'rgb.png'))[0, 0, 0], brightness)
            self.assertEqual(meta['label_feature_counts']['flooded_building'], 1)
            self.assertGreater(np.asarray(Image.open(folder / 'building.png'))[:, :, 3].sum(), 0)
            timestamp = (folder / 'rgb.png').stat().st_mtime_ns
            p.get(self.sid, slot)
            self.assertEqual((folder / 'rgb.png').stat().st_mtime_ns, timestamp)

    def test_corrupt_image_isolated(self):
        path = self.m.resolve(self.m.samples[self.sid]['images']['pre']['path'])
        path.write_bytes(b'invalid tiff')
        p = Previews(self.m, self.root / 'previews')
        self.assertIn('Sample Load Error', p.get(self.sid, 'pre')['error'])
        self.assertNotIn('error', p.get(self.sid, 'post1'))
        self.store.save(self.sid, self.payload(decision='needs_review', selected_post=None))

    def test_integrity_hash_missing_duplicate_unknown(self):
        self.m.resolve(self.m.samples[self.sid]['images']['post2']['path']).unlink()
        self.m.resolve(self.m.samples[self.sid]['images']['pre']['path']).write_bytes(b'bad')
        self.m.issues.append({'code': 'DUPLICATE_SAMPLE_ID'})
        self.store.issues.append({'code': 'UNKNOWN_OR_DUPLICATE_LEGACY_REVIEW'})
        result = integrity(self.m, self.store)
        self.assertFalse(result['valid'])
        self.assertTrue({'HASH_MISMATCH', 'MISSING_FILE', 'DUPLICATE_SAMPLE_ID', 'UNKNOWN_OR_DUPLICATE_LEGACY_REVIEW'} <= {i['code'] for i in result['issues']})

    def test_http_security_and_persistence(self):
        with TestClient(create_app(self.m.path, self.root / 'http库', self.root)) as client:
            b = client.get('/api/bootstrap').json()
            self.assertEqual(b['summary']['pending'], 3)
            self.assertEqual(client.post('/api/review/'+self.sid, json=self.payload()).status_code, 403)
            saved = client.post('/api/review/'+self.sid, headers={'X-Review-Token': b['token']}, json=self.payload())
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(client.get('/api/sample/'+self.sid).json()['record']['decision'], 'accepted')
            self.assertEqual(client.get('/api/sample/missing').status_code, 404)
            self.assertEqual(client.get('/preview/x/pre/../../secret').status_code, 404)
            self.assertEqual(client.get('/', headers={'Host': 'evil.example'}).status_code, 403)

    def test_real_20_readonly_compatibility(self):
        legacy = DEFAULT / 'top20_visual_review.json'
        before = digest(legacy)
        real = Manifest()
        store = Store(real, self.root / '真实清单隔离库')
        self.assertEqual(store.summary(), {'total': 197, 'accepted': 8, 'rejected': 12,
                         'needs_review': 0, 'pending': 177, 'selected_post1': 3, 'selected_post2': 5, 'review_complete': False})
        self.assertEqual(sum('legacy_record' in r for r in store.states.values()), 20)
        for r in store.states.values():
            if 'legacy_record' in r:
                self.assertEqual(r['notes'], r['legacy_record']['reason'])
        self.assertEqual(digest(legacy), before)

    def test_incomplete_report(self):
        target = self.root / '报告.md'
        report(self.m, self.store, target)
        text = target.read_text(encoding='utf-8')
        self.assertIn('INCOMPLETE', text)
        self.assertIn(self.m.sha256, text)

    def test_real_duplicate_manifest_detection(self):
        doc = json.loads(self.m.path.read_text(encoding='utf-8'))
        doc['entries'].append(copy.deepcopy(doc['entries'][0]))
        atomic_json(self.m.path, doc)
        duplicate = Manifest(self.m.path, self.root)
        self.assertEqual(duplicate.total_entries, 4)
        self.assertEqual(duplicate.issues[0]['code'], 'DUPLICATE_SAMPLE_ID')

    def test_unknown_snapshot_review_reported_and_preserved(self):
        doc = self.store.snapshot_value()
        doc['reviews']['unknown'] = copy.deepcopy(self.store.states[self.sid])
        doc['reviews']['unknown']['sample_id'] = 'unknown'
        atomic_json(self.store.snapshot, doc)
        fresh = Store(self.m, self.store.directory)
        result = integrity(self.m, fresh)
        self.assertIn('INVALID_SNAPSHOT_REVIEW', {i['code'] for i in result['issues']})
        self.assertTrue((fresh.directory / 'snapshot_before_recovery.json').exists())

    def test_saved_selection_missing_asset_still_loads(self):
        self.store.save(self.sid, self.payload(selected_post='post2'))
        self.m.resolve(self.m.samples[self.sid]['images']['post2']['path']).unlink()
        fresh = Store(self.m, self.store.directory)
        self.assertEqual(fresh.states[self.sid]['selected_post'], 'post2')
        self.assertFalse(integrity(self.m, fresh)['valid'])
        fresh.save(self.sid, self.payload(decision='needs_review', selected_post=None))

    def test_flags_type_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid flags'):
            self.store.save(self.sid, self.payload(flags=[]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
