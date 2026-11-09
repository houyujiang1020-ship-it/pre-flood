"""D: replace only road Dice with FP/FN-asymmetric Tversky."""
import math
import torch

def overlap_components(logits,truth,valid,alpha=.4,beta=.6):
    if not all(math.isfinite(x) and x>0 for x in (alpha,beta)) or abs(alpha+beta-1)>1e-12:
        raise ValueError('Positive alpha/beta must sum to one')
    mask=valid.unsqueeze(1)
    p=logits.sigmoid()*mask;target=truth*mask
    tp=(p*target).sum((0,2,3));den=(p+target).sum((0,2,3))
    dice=1-(2*tp+1)/(den+1)
    fp=(p*(1-target)).sum((0,2,3))
    fn=((1-p)*target).sum((0,2,3))
    tversky=1-(tp+.5)/(tp+alpha*fp+beta*fn+.5)
    return dice,torch.cat((dice[:2],tversky[2:]))

def road_tversky_loss(logits,truth,valid,pos_weight=None,dice_weight=.5,alpha=.4,beta=.6):
    if valid.sum().item()<=0:raise ValueError('Tile has no valid supervision')
    if pos_weight is not None:raise ValueError('D forbids positive class weights')
    bce=(torch.nn.functional.binary_cross_entropy_with_logits(logits,truth,reduction='none',pos_weight=None)*valid.unsqueeze(1)).sum()/(valid.sum()*4)
    _,components=overlap_components(logits,truth,valid,alpha,beta)
    loss=bce+dice_weight*components.mean()
    if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss')
    return loss

def assert_d_configuration(config,baseline):
    differences={k for k in set(config)|set(baseline) if config.get(k)!=baseline.get(k)}
    if differences!={'road_overlap_loss','model_id','output_dir'}:
        raise ValueError('Undeclared configuration differences: '+str(differences))
    if config['road_overlap_loss']!={'type':'road_tversky_replacement','channels':[2,3],'alpha_fp':.4,'beta_fn':.6,'smoothing':.5}:
        raise ValueError('Road loss differs from preregistration')
    if baseline.get('dice_weight')!=.5 or baseline.get('balanced_loss') is not False:
        raise ValueError('Baseline loss audit mismatch')
    if config['splits'].get('test') or any(x['area']!='Germany_Training_Public' for v in config['splits'].values() for x in v):
        raise ValueError('Germany train/validation only')
