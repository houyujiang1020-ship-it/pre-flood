"""Train-only class-aware index scheduling; batch size stays with the trainer."""
import random

CLASSES=('non_flooded_building','flooded_building','non_flooded_road','flooded_road')
class ClassAwareSampler:
    def __init__(self, tiles, config, seed=42):
        self.tiles=list(tiles);self.seed=int(seed)
        if not self.tiles or any(x.get('split')!='train' for x in self.tiles):
            raise ValueError('Nonempty train split required')
        if len({(x['area'],x['label']) for x in self.tiles})!=len(self.tiles):
            raise ValueError('Duplicate sample identity')
        if config.get('type')!='class_aware': raise ValueError('Unsupported sampler')
        for x in self.tiles:
            if any(type(x.get(c)) is not bool for c in CLASSES): raise ValueError('Boolean class flags required')
        self.steps=config.get('epoch_size',len(self.tiles))
        if type(self.steps) is not int or self.steps<1: raise ValueError('Invalid epoch_size')
        self.groups=config.get('groups',{'flooded_road':2,'flooded_building':2,'foreground':1,'random':1})
        if not self.groups or set(self.groups)-{'flooded_road','flooded_building','foreground','random'}:
            raise ValueError('Invalid groups')
        if any(type(v) is not int or v<0 for v in self.groups.values()) or not sum(self.groups.values()):
            raise ValueError('Group slots must be nonnegative integers, with positive total')
        self.pools={c:[i for i,x in enumerate(self.tiles) if x[c]] for c in ('flooded_road','flooded_building')}
        self.pools['foreground']=[i for i,x in enumerate(self.tiles) if any(x[c] for c in CLASSES)]
        self.pools['random']=list(range(len(self.tiles)))
        self.missing=[c for c,v in self.groups.items() if v and not self.pools[c]]
        # Missing classes fall back explicitly to random; never synthesize indices.
        self.cycle=[c for c,v in self.groups.items() for _ in range(v)]
    def sample(self,epoch):
        if type(epoch) is not int or epoch<0: raise ValueError('Invalid epoch')
        rng=random.Random(self.seed+epoch)
        selected=[];sources=[];bags={}
        def draw(group):
            actual=group if self.pools[group] else 'random'
            if not bags.get(actual):
                bags[actual]=self.pools[actual].copy();rng.shuffle(bags[actual])
            return bags[actual].pop()
        while len(selected)<self.steps:
            cycle=self.cycle.copy();rng.shuffle(cycle)
            for group in cycle:
                if len(selected)==self.steps:break
                selected.append(draw(group));sources.append(group)
        counts={c:sum(self.tiles[i][c] for i in selected) for c in CLASSES}
        unique=set(selected)
        return selected,{'epoch':epoch+1,'seed':self.seed+epoch,'epoch_size':self.steps,
            'class_sample_exposure_count':counts,'category_appearances':counts,
            'available_class_tiles':{c:sum(x[c] for x in self.tiles) for c in CLASSES},
            'group_draw_counts':{c:sources.count(c) for c in self.groups},
            'missing_groups_fallback_to_random':self.missing,'unique_tiles_sampled':len(unique),
            'coverage_fraction':len(unique)/len(self.tiles),'sample_indices':selected,'source_groups':sources,
            'cycle_length':len(self.cycle),'batch_size':1,
            'exposure_scope':'Multi-label counts; rare-group guarantee per complete cycle, not every single-image batch.'}

def class_tiles(area,row,labels,valid):
    if valid.sum().item()<=0:raise ValueError('No valid supervision')
    flags=((labels>0)&(valid.unsqueeze(0)>0)).sum((1,2)).gt(0).tolist()
    return {'area':str(area),'label':row['label'],'split':'train',**dict(zip(CLASSES,flags))}
