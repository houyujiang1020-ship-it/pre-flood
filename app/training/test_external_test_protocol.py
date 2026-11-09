import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from scripts.freeze_external_test import build_manifest, canonical_sha, sha256
from scripts.evaluate_external_test_once import verify_manifest as verify_labeled_manifest
from scripts.freeze_unlabeled_external_test import build_manifest as build_unlabeled_manifest
from scripts.run_unlabeled_blind_inference_once import verify_manifest as verify_unlabeled_manifest


def write_tif(path, west, north):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, 'w', driver='GTiff', width=4, height=4, count=3, dtype='uint8',
                       crs='EPSG:4326', transform=from_origin(west, north, .01, .01)) as image:
        image.write(np.ones((3, 4, 4), dtype=np.uint8))


def write_area(root, name, west, include_flooded_road=True):
    area = root / name
    write_tif(area / 'PRE-event/pre.tif', west, 10)
    write_tif(area / 'POST-event/post.tif', west, 10)
    features = [
        {'type': 'Feature', 'properties': {'building': 'yes', 'flooded': 'no'}, 'geometry': None},
        {'type': 'Feature', 'properties': {'building': 'yes', 'flooded': 'yes'}, 'geometry': None},
        {'type': 'Feature', 'properties': {'highway': 'primary', 'flooded': 'no'}, 'geometry': None},
    ]
    if include_flooded_road:
        features.append({'type': 'Feature', 'properties': {'highway': 'primary', 'flooded': 'yes'},
                         'geometry': None})
    (area / 'annotations').mkdir(parents=True)
    (area / 'annotations/label.geojson').write_text(
        json.dumps({'type': 'FeatureCollection', 'features': features}), encoding='utf-8')
    with (area / f'{name}_label_image_mapping.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['label', 'pre-event image', 'post-event image 1'])
        writer.writeheader()
        writer.writerow({'label': 'label.geojson', 'pre-event image': 'pre.tif',
                         'post-event image 1': 'post.tif'})
    return area


def make_fixture(tmp_path, test_west=20, include_flooded_road=True):
    data = tmp_path / 'external'
    write_area(data, 'External_Test', test_west, include_flooded_road)
    reference_root = tmp_path / 'known'
    write_area(reference_root, 'Known_Development', 0)
    config = {
        'data_root': 'known',
        'splits': {'train': [{'area': 'Known_Development', 'label': 'label.geojson'}],
                   'validation': [], 'test': []},
    }
    config_path = tmp_path / 'reference.json'
    config_path.write_text(json.dumps(config), encoding='utf-8')
    (tmp_path / 'candidate.pth').write_bytes(b'candidate')
    (tmp_path / 'baseline.pth').write_bytes(b'baseline')
    (tmp_path / 'source.html').write_text('publisher source evidence', encoding='utf-8')
    (tmp_path / 'license.txt').write_text('license evidence', encoding='utf-8')
    request = {
        'dataset_name': 'Independent fixture', 'publisher': 'Test publisher',
        'source_url': 'https://example.test/data', 'license_name': 'CC-BY-4.0',
        'license_url': 'https://example.test/license', 'region_id': 'external-region',
        'event_id': 'external-event', 'event_date': '2026-09-01',
        'downloaded_at': '2026-09-26T00:00:00Z',
        'source_evidence_path': str(tmp_path / 'source.html'),
        'license_evidence_path': str(tmp_path / 'license.txt'),
        'dataset_root': str(data), 'areas': ['External_Test'],
        'post_event_column': 'post-event image 1', 'labels_available': True,
        'purpose': 'independent_model_accuracy',
        'checkpoints': {
            'candidate': {'model_id': 'candidate', 'path': 'candidate.pth'},
            'baseline': {'model_id': 'baseline', 'path': 'baseline.pth'},
        },
    }
    request_path = tmp_path / 'request.json'
    request_path.write_text(json.dumps(request), encoding='utf-8')
    return request, request_path, config_path


def make_unlabeled_fixture(tmp_path):
    _, _, config_path = make_fixture(tmp_path)
    data = tmp_path / 'unlabeled'
    (data / 'PRE-event').mkdir(parents=True)
    (data / 'POST-event').mkdir()
    table = data / 'External_Unlabeled_label_image_mapping.csv'
    with table.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['label', 'pre-event image', 'post-event image 1'])
        writer.writeheader()
        for index in range(20):
            pre_name, post_name = f'pre-{index}.tif', f'post-{index}.tif'
            write_tif(data / 'PRE-event' / pre_name, 20 + index, 10)
            write_tif(data / 'POST-event' / post_name, 20 + index, 10)
            writer.writerow({'label': f'label-{index}.geojson', 'pre-event image': pre_name,
                             'post-event image 1': post_name})
    archive = tmp_path / 'unlabeled.tar.gz'
    archive.write_bytes(b'frozen archive identity')
    request = {
        'dataset_name': 'Unlabeled fixture', 'publisher': 'Test publisher',
        'source_url': 'https://example.test/data', 'license_name': 'CC-BY-4.0',
        'license_url': 'https://example.test/license', 'region_id': 'unlabeled-region',
        'event_id': 'unlabeled-event', 'event_date': '2026-09-01',
        'downloaded_at': '2026-09-26T00:00:00Z', 'archive_path': str(archive),
        'archive_sha256': sha256(archive), 'dataset_root': str(data),
        'area_name': 'External_Unlabeled', 'labels_available': False,
        'purpose': 'blind_inference_only',
        'source_evidence_path': str(tmp_path / 'source.html'),
        'license_evidence_path': str(tmp_path / 'license.txt'),
        'checkpoint': {'model_id': 'candidate', 'path': 'candidate.pth'},
    }
    request_path = tmp_path / 'unlabeled-request.json'
    request_path.write_text(json.dumps(request), encoding='utf-8')
    return request, request_path, config_path


class ExternalTestProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_freeze_seals_complete_nonoverlapping_test(self):
        request, request_path, config = make_fixture(self.tmp_path)
        manifest = build_manifest(request, request_path, [config], root=self.tmp_path)
        seal = manifest.pop('seal_sha256')
        self.assertEqual(seal, canonical_sha(manifest))
        self.assertEqual(manifest['pair_count'], 1)
        self.assertEqual(manifest['spatial_overlap_count'], 0)
        self.assertTrue(all(manifest['feature_support'][name] == 1 for name in manifest['feature_support']))
        self.assertFalse(manifest['inference_performed'])
        self.assertFalse(manifest['production_ready'])

    def test_freeze_rejects_spatial_overlap(self):
        request, request_path, config = make_fixture(self.tmp_path, test_west=0)
        with self.assertRaisesRegex(ValueError, 'spatially overlaps'):
            build_manifest(request, request_path, [config], root=self.tmp_path)

    def test_freeze_rejects_missing_class_support(self):
        request, request_path, config = make_fixture(self.tmp_path, include_flooded_road=False)
        with self.assertRaisesRegex(ValueError, 'Every class'):
            build_manifest(request, request_path, [config], root=self.tmp_path)

    def test_evaluator_detects_manifest_tampering(self):
        request, request_path, config = make_fixture(self.tmp_path)
        manifest = build_manifest(request, request_path, [config], root=self.tmp_path)
        path = self.tmp_path / 'manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertEqual(verify_labeled_manifest(path)['pair_count'], 1)
        value = json.loads(path.read_text(encoding='utf-8'))
        value['pair_count'] = 2
        path.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'seal differs'):
            verify_labeled_manifest(path)

    def test_unlabeled_freeze_and_inference_verifier_preserve_no_accuracy_boundary(self):
        request, request_path, config = make_unlabeled_fixture(self.tmp_path)
        manifest = build_unlabeled_manifest(request, request_path, [config], root=self.tmp_path)
        self.assertEqual(manifest['pair_count'], 20)
        self.assertEqual(manifest['spatial_overlap_count'], 0)
        self.assertFalse(manifest['labels_available'])
        self.assertFalse(manifest['accuracy_verified'])
        self.assertFalse(manifest['production_ready'])
        path = self.tmp_path / 'unlabeled-manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        verified = verify_unlabeled_manifest(path)
        self.assertEqual(verified['seal_sha256'], manifest['seal_sha256'])

    def test_unlabeled_inference_verifier_detects_manifest_tampering(self):
        request, request_path, config = make_unlabeled_fixture(self.tmp_path)
        manifest = build_unlabeled_manifest(request, request_path, [config], root=self.tmp_path)
        manifest['protocol']['thresholds']['flooded_road'] = .4
        path = self.tmp_path / 'tampered-unlabeled-manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'seal differs'):
            verify_unlabeled_manifest(path)


if __name__ == '__main__':
    unittest.main()
