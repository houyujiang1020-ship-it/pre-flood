import unittest
import tempfile
import json
from pathlib import Path
from class_aware_sampler import ClassAwareSampler, CLASSES

def tile(i,flags):
    return {'area':'中文路径/德国','label':str(i),'split':'train',**dict(zip(CLASSES,flags))}
class ClassAwareTests(unittest.TestCase):
    def setUp(self):
        self.tiles=[tile(0,[True,False,True,False]),tile(1,[False,True,True,True]),tile(2,[False,False,False,False])]
        self.config={'type':'class_aware','epoch_size':98,'groups':{'flooded_road':2,'flooded_building':2,'foreground':1,'random':1}}
    def test_rare_present_and_cycle_exposure(self):
        indices,r=ClassAwareSampler(self.tiles,self.config).sample(0)
        for start in range(0,96,6):
            block=indices[start:start+6]
            self.assertTrue(any(self.tiles[i]['flooded_road'] for i in block))
            self.assertTrue(any(self.tiles[i]['flooded_building'] for i in block))
    def test_rare_missing(self):
        indices,r=ClassAwareSampler([self.tiles[0]],self.config).sample(0)
        self.assertEqual(set(indices),{0})
        self.assertEqual(set(r['missing_groups_fallback_to_random']),{'flooded_road','flooded_building'})
    def test_multilabel_counts(self):
        indices,r=ClassAwareSampler(self.tiles,self.config).sample(2)
        for c in CLASSES:self.assertEqual(r['class_sample_exposure_count'][c],sum(self.tiles[i][c] for i in indices))
    def test_small_single_image_batch(self):
        for size in [1,2,3,5]:
            indices,r=ClassAwareSampler(self.tiles,{**self.config,'epoch_size':size}).sample(0)
            self.assertEqual(len(indices),size)
            self.assertEqual(r['batch_size'],1)
    def test_seed_reproducibility(self):
        a=ClassAwareSampler(self.tiles,self.config,19)
        self.assertEqual(a.sample(1),ClassAwareSampler(self.tiles,self.config,19).sample(1))
        self.assertNotEqual(a.sample(0)[0],a.sample(1)[0])
    def test_epoch_statistics_and_indices(self):
        a=ClassAwareSampler(self.tiles,self.config)
        for epoch in range(10):
            indices,r=a.sample(epoch)
            self.assertEqual(r['epoch'],epoch+1)
            self.assertEqual(sum(r['group_draw_counts'].values()),98)
            self.assertTrue(all(type(i) is int and 0<=i<len(self.tiles) for i in indices))
    def test_chinese_path(self):
        with tempfile.TemporaryDirectory(prefix='类别采样') as d:
            p=Path(d)/'样本.json';p.write_text(json.dumps(self.tiles),encoding='utf-8')
            self.assertEqual(ClassAwareSampler(json.loads(p.read_text()),self.config).sample(0),ClassAwareSampler(self.tiles,self.config).sample(0))
    def test_invalid_and_holdout(self):
        for tiles in [[],[{**self.tiles[0],'split':'validation'}],self.tiles+[self.tiles[0]]]:
            with self.assertRaises(ValueError):ClassAwareSampler(tiles,self.config)
        for groups in [{'fake':1},{'random':-1},{'random':0},{'random':.5}]:
            with self.assertRaises(ValueError):ClassAwareSampler(self.tiles,{**self.config,'groups':groups})
if __name__=='__main__':unittest.main()
