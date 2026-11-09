"""Deterministic train-only sampler balancing geographic domains and classes."""
import random
from pathlib import Path

from positive_sampler import PositiveSampler


class DomainBalancedPositiveSampler:
    def __init__(self, tiles, config, seed=42):
        self.tiles = list(tiles)
        if not self.tiles or any(t.get('split') != 'train' for t in self.tiles):
            raise ValueError('Nonempty train split required')
        if len({(t['area'], t['label']) for t in self.tiles}) != len(self.tiles):
            raise ValueError('Duplicate sample identity')
        if config.get('type') != 'domain_balanced_positive':
            raise ValueError('Unsupported sampler type')
        self.seed = int(seed)
        self.steps = config.get('epoch_size', len(self.tiles))
        weights = config.get('domain_weights', {})
        self.domain_keys = [Path(t['area']).name for t in self.tiles]
        domains = sorted(set(self.domain_keys))
        if set(weights) != set(domains) or any(type(v) not in (int, float) or v <= 0 for v in weights.values()):
            raise ValueError('Every training domain requires a positive weight')
        if type(self.steps) is not int or self.steps < len(domains):
            raise ValueError('epoch_size must cover every domain')
        total = sum(weights.values())
        raw = {d: self.steps * weights[d] / total for d in domains}
        counts = {d: int(raw[d]) for d in domains}
        for d in sorted(domains, key=lambda x: (raw[x] - counts[x], x), reverse=True)[:self.steps - sum(counts.values())]:
            counts[d] += 1
        if any(v < 1 for v in counts.values()):
            raise ValueError('A domain received no samples')
        self.domains = domains
        self.counts = counts
        inner = config.get('inner_positive_aware', {})
        self.samplers = {}
        self.local_to_global = {}
        for offset, domain in enumerate(domains):
            indices = [i for i, key in enumerate(self.domain_keys) if key == domain]
            self.local_to_global[domain] = indices
            local = [self.tiles[i] for i in indices]
            local_config = dict(inner, type='positive_aware', epoch_size=counts[domain])
            self.samplers[domain] = PositiveSampler(local, local_config, self.seed + 100003 * offset)

    def sample(self, epoch):
        if type(epoch) is not int or epoch < 0:
            raise ValueError('Invalid epoch')
        selected = []
        reports = {}
        for domain in self.domains:
            local, report = self.samplers[domain].sample(epoch)
            selected.extend(self.local_to_global[domain][i] for i in local)
            reports[domain] = report
        random.Random(self.seed + epoch).shuffle(selected)
        return selected, {
            'epoch': epoch + 1, 'seed': self.seed + epoch, 'epoch_size': self.steps,
            'sampler_type': 'domain_balanced_positive', 'domain_appearances': self.counts,
            'domain_available_tiles': {d: len(self.local_to_global[d]) for d in self.domains},
            'domain_reports': reports, 'unique_tiles_sampled': len(set(selected)),
            'coverage_fraction': len(set(selected)) / len(self.tiles),
            'sample_indices': selected,
        }
