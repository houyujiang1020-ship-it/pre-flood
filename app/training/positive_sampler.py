"""Deterministic train-only sampling with explicit overlapping category quotas.

Quotas count tile appearances (sampling with replacement), not unique tiles or
pixel balance. Coverage is reported separately. No torch/GPU dependency.
"""
import math
import random

CATEGORIES = ('has_flooded_building', 'has_flooded_road', 'has_building', 'has_road', 'background_only')


def tile_categories(area, row, labels, valid):
    counts = ((labels > 0) & (valid.unsqueeze(0) > 0)).sum(dim=(1, 2)).tolist()
    if valid.sum().item() <= 0:
        raise ValueError('Tile has no valid supervision')
    return dict(split='train', area=str(area), label=row['label'],
                has_flooded_building=counts[1] > 0, has_flooded_road=counts[3] > 0,
                has_building=counts[0] + counts[1] > 0,
                has_road=counts[2] + counts[3] > 0, background_only=sum(counts) == 0)


class PositiveSampler:
    def __init__(self, tiles, config, seed=42):
        self.tiles = list(tiles)
        if not self.tiles or any(t.get('split') != 'train' for t in self.tiles):
            raise ValueError('Sampler accepts nonempty train split only; validation/holdout forbidden')
        identities = [(t['area'], t['label']) for t in self.tiles]
        if len(set(identities)) != len(identities):
            raise ValueError('Duplicate training tile identity')
        for tile in self.tiles:
            if any(type(tile.get(c)) is not bool for c in CATEGORIES):
                raise ValueError('All category flags must be booleans')
            if (tile['has_flooded_building'] and not tile['has_building'] or
                tile['has_flooded_road'] and not tile['has_road'] or
                tile['background_only'] != (not tile['has_building'] and not tile['has_road'])):
                raise ValueError('Inconsistent category flags')
        if config.get('type') != 'positive_aware':
            raise ValueError('Unsupported sampler type')
        self.seed = int(seed)
        self.steps = config.get('epoch_size', len(self.tiles))
        if type(self.steps) is not int or self.steps < 1:
            raise ValueError('epoch_size must be a positive integer')
        ratios = config.get('min_fractions', {})
        if set(ratios) - set(CATEGORIES):
            raise ValueError('Unknown category quota')
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in ratios.values()):
            raise ValueError('Quota fractions must be finite and between 0 and 1')
        cap = config.get('max_background_fraction', 1.0)
        if not isinstance(cap, (int, float)) or not math.isfinite(cap) or not 0 <= cap <= 1:
            raise ValueError('Background cap must be between 0 and 1')
        self.background_cap = math.floor(cap * self.steps)
        self.minimum = {c: math.ceil(ratios.get(c, 0) * self.steps) for c in CATEGORIES}
        self.pools = {c: [i for i, t in enumerate(self.tiles) if t[c]] for c in CATEGORIES}
        for c in CATEGORIES:
            if self.minimum[c] and not self.pools[c]:
                raise ValueError('Required category absent in train: ' + c)
        if self.minimum['background_only'] > self.background_cap:
            raise ValueError('Background quota exceeds cap')
        if not any(not t['background_only'] for t in self.tiles) and self.background_cap < self.steps:
            raise ValueError('Background cap impossible for all-background training split')

    def sample(self, epoch):
        if type(epoch) is not int or epoch < 0:
            raise ValueError('epoch must be a nonnegative integer')
        rng = random.Random(self.seed + epoch)
        selected, counts = [], dict.fromkeys(CATEGORIES, 0)

        def add(index):
            selected.append(index)
            for c in CATEGORIES:
                counts[c] += int(self.tiles[index][c])

        # Satisfy rare categories first; overlap contributes to every quota.
        for category in sorted(CATEGORIES, key=lambda c: (len(self.pools[c]), c)):
            while counts[category] < self.minimum[category]:
                if len(selected) >= self.steps:
                    raise ValueError('Quotas exceed epoch capacity; lower fractions or increase epoch_size')
                add(rng.choice(self.pools[category]))
        while len(selected) < self.steps:
            eligible = [i for i, tile in enumerate(self.tiles)
                        if not tile['background_only'] or counts['background_only'] < self.background_cap]
            add(rng.choice(eligible))
        rng.shuffle(selected)
        unique = set(selected)
        report = {'epoch': epoch + 1, 'seed': self.seed + epoch, 'epoch_size': self.steps,
                  'sampling_with_replacement': True, 'available_tiles': len(self.tiles),
                  'unique_tiles_sampled': len(unique), 'coverage_fraction': len(unique) / len(self.tiles),
                  'available_category_tiles': {c: len(self.pools[c]) for c in CATEGORIES},
                  'minimum_category_appearances': self.minimum, 'category_appearances': counts,
                  'unique_category_tiles': {c: sum(self.tiles[i][c] for i in unique) for c in CATEGORIES},
                  'max_background_appearances': self.background_cap}
        return selected, report
