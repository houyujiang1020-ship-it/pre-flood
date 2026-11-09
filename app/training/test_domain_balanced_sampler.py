import unittest

from domain_balanced_sampler import DomainBalancedPositiveSampler


def tile(domain, index, flooded=False):
    return {'area': domain, 'label': str(index), 'split': 'train',
            'has_flooded_building': flooded, 'has_flooded_road': flooded,
            'has_building': True, 'has_road': True, 'background_only': False}


class DomainBalancedSamplerTests(unittest.TestCase):
    def setUp(self):
        self.tiles = [tile('Germany', i, i == 0) for i in range(4)] + [tile('Louisiana', i, i < 2) for i in range(8)]
        self.config = {'type': 'domain_balanced_positive', 'epoch_size': 20,
                       'domain_weights': {'Germany': 1, 'Louisiana': 1},
                       'inner_positive_aware': {'min_fractions': {'has_flooded_road': .2},
                                                'max_background_fraction': .1}}

    def test_equal_domain_appearances_and_rare_coverage(self):
        indices, report = DomainBalancedPositiveSampler(self.tiles, self.config, 7).sample(0)
        self.assertEqual(report['domain_appearances'], {'Germany': 10, 'Louisiana': 10})
        self.assertEqual({d: sum(self.tiles[i]['area'] == d for i in indices) for d in report['domain_appearances']}, report['domain_appearances'])
        for domain in report['domain_reports'].values():
            self.assertGreaterEqual(domain['category_appearances']['has_flooded_road'], 2)

    def test_deterministic_and_epoch_changes(self):
        one = DomainBalancedPositiveSampler(self.tiles, self.config, 7)
        self.assertEqual(one.sample(2), DomainBalancedPositiveSampler(self.tiles, self.config, 7).sample(2))
        self.assertNotEqual(one.sample(1)[0], one.sample(2)[0])

    def test_absolute_area_paths_use_directory_name(self):
        tiles = [{**t, 'area': 'C:/datasets/' + t['area']} for t in self.tiles]
        _, report = DomainBalancedPositiveSampler(tiles, self.config, 7).sample(0)
        self.assertEqual(report['domain_appearances'], {'Germany': 10, 'Louisiana': 10})

    def test_rejects_invalid_domains_and_holdout(self):
        with self.assertRaises(ValueError):
            DomainBalancedPositiveSampler(self.tiles, {**self.config, 'domain_weights': {'Germany': 1}})
        with self.assertRaises(ValueError):
            DomainBalancedPositiveSampler([{**self.tiles[0], 'split': 'validation'}], self.config)


if __name__ == '__main__':
    unittest.main()
