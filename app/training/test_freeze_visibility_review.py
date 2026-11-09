import unittest
from pathlib import Path
from types import SimpleNamespace
from freeze_visibility_review import freeze_selection, training_config
from train_full import validate_frozen_dataset


class FrozenReviewTests(unittest.TestCase):
    def sample(self, split, post2=True):
        return {'split': split, 'label': str(Path('11') / ('Area_' + split) / 'annotations' / (split + '.geojson')),
                'images': {'post1': {'sha256': 'a'}, 'post2': {'sha256': 'b'} if post2 else None}}

    def test_only_accepted_samples_are_frozen_with_human_post(self):
        manifest = SimpleNamespace(samples={'Germany_train': self.sample('train'),
                                             'Germany_validation': self.sample('validation'),
                                             'Germany_reject': self.sample('train')})
        store = SimpleNamespace(summary=lambda: {'review_complete': True, 'pending': 0, 'needs_review': 0},
                                states={'Germany_train': {'decision': 'accepted', 'selected_post': 'post2'},
                                        'Germany_validation': {'decision': 'accepted', 'selected_post': 'post1'},
                                        'Germany_reject': {'decision': 'rejected', 'selected_post': None}})
        splits, rejected = freeze_selection(manifest, store)
        self.assertEqual(splits['train'][0]['post_event_column'], 'post-event image 2')
        self.assertEqual(splits['validation'][0]['post_event_column'], 'post-event image 1')
        self.assertEqual(rejected, ['Germany_reject'])
        self.assertEqual(splits['test'], [])

    def test_incomplete_review_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            freeze_selection(SimpleNamespace(samples={}), SimpleNamespace(summary=lambda: {
                'review_complete': False, 'pending': 1, 'needs_review': 0}))

    def test_two_configs_do_not_combine_rebalancing_or_test(self):
        splits = {'train': [{'area': 'A', 'label': 'a'}], 'validation': [{'area': 'B', 'label': 'b'}], 'test': []}
        weighted = training_config(splits, Path('cache'), 'out-a', 'a', False)
        sampled = training_config(splits, Path('cache'), 'out-b', 'b', True)
        self.assertTrue(weighted['balanced_loss'])
        self.assertNotIn('sampler', weighted)
        self.assertFalse(sampled['balanced_loss'])
        self.assertIn('sampler', sampled)
        self.assertEqual(weighted['splits']['test'], [])
        self.assertIn('No Louisiana', sampled['test_scope'])

    def test_frozen_evidence_change_is_rejected(self):
        import hashlib, json, tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, value in [('state.json', b'state'), ('reviews.jsonl', b'review'), ('manifest.json', b'manifest')]:
                (root / name).write_bytes(value)
            splits = {'train': [{'area': 'A', 'label': 'a'}], 'validation': [{'area': 'B', 'label': 'b'}], 'test': []}
            split_hash = hashlib.sha256(json.dumps(splits, sort_keys=True).encode()).hexdigest()
            frozen = {'training_split_frozen': True, 'review_complete': True, 'dataset_split_hash': split_hash}
            for path_key, hash_key, name in [('review_state_path', 'review_state_sha256', 'state.json'),
                                              ('reviews_jsonl_path', 'reviews_jsonl_sha256', 'reviews.jsonl'),
                                              ('visibility_manifest_path', 'manifest_sha256', 'manifest.json')]:
                frozen[path_key] = name
                frozen[hash_key] = hashlib.sha256((root / name).read_bytes()).hexdigest()
            (root / 'frozen.json').write_text(json.dumps(frozen), encoding='utf-8')
            config = {'splits': splits, 'frozen_dataset_manifest': 'frozen.json', 'frozen_dataset_sha256': split_hash}
            self.assertTrue(validate_frozen_dataset(config, root)['training_split_frozen'])
            (root / 'reviews.jsonl').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                validate_frozen_dataset(config, root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
