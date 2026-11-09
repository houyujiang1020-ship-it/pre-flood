import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app' / 'training'))
from positive_sampler import PositiveSampler


def tile(index, flooded=False, background=False, split='train'):
    return dict(area='area', label=str(index), split=split,
                has_flooded_building=flooded, has_flooded_road=flooded,
                has_building=not background, has_road=not background, background_only=background)


class PositiveSamplerTests(unittest.TestCase):
    def setUp(self):
        self.tiles = [tile(0, flooded=True)] + [tile(i, background=i > 3) for i in range(1, 20)]
        self.config = dict(type='positive_aware', epoch_size=40,
                           min_fractions={'has_flooded_building': .5, 'has_flooded_road': .5},
                           max_background_fraction=.1)

    def test_reproducible_independent_of_previous_epochs(self):
        sampler = PositiveSampler(self.tiles, self.config, seed=12)
        expected = sampler.sample(5)
        sampler.sample(1)
        self.assertEqual(expected, PositiveSampler(self.tiles, self.config, seed=12).sample(5))
        self.assertNotEqual(expected[0], sampler.sample(6)[0])

    def test_rare_classes_guaranteed_and_background_capped(self):
        for epoch in range(30):
            indices, report = PositiveSampler(self.tiles, self.config).sample(epoch)
            self.assertEqual(len(indices), 40)
            self.assertGreaterEqual(sum(self.tiles[i]['has_flooded_building'] for i in indices), 20)
            self.assertGreaterEqual(report['category_appearances']['has_flooded_road'], 20)
            self.assertLessEqual(sum(self.tiles[i]['background_only'] for i in indices), 4)
            self.assertEqual(report['unique_tiles_sampled'], len(set(indices)))

    def test_absent_class_rejected(self):
        with self.assertRaisesRegex(ValueError, 'absent'):
            PositiveSampler(self.tiles[1:], self.config)

    def test_non_train_and_duplicate_rejected(self):
        for split in ('validation', 'test', 'holdout', None):
            with self.assertRaisesRegex(ValueError, 'train split only'):
                PositiveSampler(self.tiles + [tile(99, split=split)], self.config)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            PositiveSampler(self.tiles + [self.tiles[0]], self.config)

    def test_impossible_background_cap_and_invalid_quota_rejected(self):
        with self.assertRaisesRegex(ValueError, 'impossible'):
            PositiveSampler([tile(0, background=True)], dict(type='positive_aware', max_background_fraction=.5))
        with self.assertRaisesRegex(ValueError, 'finite'):
            PositiveSampler(self.tiles, dict(type='positive_aware', min_fractions={'has_road': float('nan')}))


if __name__ == '__main__':
    unittest.main()
