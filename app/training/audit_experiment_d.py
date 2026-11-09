"""Read-only C sealing and source-grounded baseline loss audit, before D training."""
import ast,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    d=ROOT/'experiments/diagnostics/experiment-d-preflight-20260912';d.mkdir(parents=True,exist_ok=True)
    cdir=ROOT/'models/experiments/germany-reviewed-gn-class-aware-sampler-20260912'
    parsed={p.name:json.loads(p.read_text(encoding='utf-8-sig')) for p in cdir.glob('*.json')}
    assert len(parsed['history.json'])==40 and parsed['completion_manifest.json']['promoted'] is False
    for name,value in parsed['completion_manifest.json']['artifact_sha256'].items():assert sha(cdir/name)==value,name
    hashes={str(p.relative_to(ROOT)):sha(p) for p in cdir.iterdir() if p.is_file()}
    for folder in ['models/candidates/germany-reviewed-v1','models/experiments/germany-reviewed-gn-sampler-20260912']:
        for p in (ROOT/folder).iterdir():
            if p.is_file():hashes[str(p.relative_to(ROOT))]=sha(p)
    seal={'status':'completed','promotion':'rejected','protected_sha256':hashes,'C_json_read':list(parsed),'production_ready':False}
    (d/'protected-artifacts.json').write_text(json.dumps(seal,indent=2),encoding='utf-8')
    (ROOT/'docs/EXPERIMENT_C_FINAL.md').write_text('''# Experiment C final seal

status=completed
promotion=rejected
production_ready=false

C completed 40 epochs; best epoch=40. Original files were read and hashed without modification. All entries in its completion manifest were verified.

Reasons:
- frozen development thresholds underperform baseline (macro IoU 0.107021 vs 0.133868)
- new same-validation calibration does not establish improvement (0.122391 vs baseline 0.133868)
- two-fold threshold OOF underperforms old sampler (0.103920 vs 0.114051)
- flooded-building and road priority metrics regress at fixed development thresholds and OOF

The complete manifest, history, evaluation, development calibration, OOF, sample exposure and completion manifest were read. Seal hashes: experiments/diagnostics/experiment-d-preflight-20260912/protected-artifacts.json.

Keep germany-reviewed-v1 (old sampler epoch 37) as the development baseline. No C artifacts or source are changed for D; D has its own runner and loss module. No production promotion. Germany split remains train98/validation18/test0; no Louisiana or future blind holdout access.
''',encoding='utf-8')
    config=json.loads((ROOT/'config/training.germany-reviewed-gn-sampler-20260912.json').read_text())
    candidate=json.loads((ROOT/'models/candidates/germany-reviewed-v1/candidate_manifest.json').read_text())
    assert config==candidate['training_configuration']
    assert config['dice_weight']==.5 and config['balanced_loss'] is False
    source=ROOT/'app/training/train_full.py';s=source.read_text(encoding='utf-8');tree=ast.parse(s)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='masked_loss')
    function=ast.get_source_segment(s,node)
    assert 'dice_weight * (1 - (2*intersection+1)/(denominator+1)).mean()' in function
    assert 'valid.sum() * 4' in function
    (d/'baseline-train_full.py.txt').write_bytes(source.read_bytes())
    audit={'status':'passed','baseline_config_sha256':sha(ROOT/'config/training.germany-reviewed-gn-sampler-20260912.json'),'baseline_manifest_sha256':sha(ROOT/'models/candidates/germany-reviewed-v1/candidate_manifest.json'),'trainer_sha256':sha(source),'masked_loss_source':function,'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'historical_Dice_0_5_consistent':True}
    (d/'loss-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    text='''# 真实损失函数审计（Experiment D 前置，2026-09-12）

审计结论：通过。当前源码、old sampler配置、germany-reviewed-v1 manifest一致：训练使用 **BCE + 0.5 × mean(per-channel Dice loss)**。没有历史Dice=0.5不一致的blocker。审计先于D训练；源码原文及哈希保存在experiments/diagnostics/experiment-d-preflight-20260912/loss-audit.json及baseline-train_full.py.txt。

## 真实训练语义

- BCE：binary_cross_entropy_with_logits，系数1；balanced_loss=false，pos_weight=None，无类别加权。
- BCE先reduction=none，乘共享有效监督mask，再对batch/channel/H/W全求和，除以4×有效mask总和。四个channel等权。
- Dice weight=0.5。独立对每个channel聚合batch/H/W，得到4个loss后算术平均。不是把4类混在一个全局Dice中。
- sigmoid：BCEWithLogits内部使用稳定的logits公式；Dice分支对logits显式sigmoid。
- mask：probability=sigmoid(logits)×mask，target=truth×mask，然后probability×target求intersection。二值valid mask下mask²=mask。源码若接收非二值mask则intersection实际含mask²；本实验继续使用原预处理的二值有效监督mask。
- smoothing：Dice分子和分母均加1，没有额外epsilon、clamp或按类别跳过。
- 空GT通道不跳过，Dice loss=1−1/(Σ有效预测概率+1)，因此惩罚该通道的FP；四类仍各占平均的1/4。
- 全无有效监督直接ValueError；损失非有限直接RuntimeError。
- flooded/non-flooded无特殊分支：四类完全同公式、同系数。
- 实际batch size=1；epoch train_loss是98个步骤loss的算术平均。
- **验证loss是BCE-only**：evaluate调用masked_loss未传dice_weight，使用默认0。保留此历史定义；不是训练目标的完整验证值。checkpoint依据validation macro IoU（threshold=0.5）最大值选择，与loss无关。

## 伪公式（binary valid mask）

z为logits，p=sigmoid(z)，y为二值GT，m为valid mask，V=Σ_bhw m。

BCE = Σ_bchw [m × BCEWithLogits(z,y)] / (4V)

TP_c = Σ_bhw m p_c y_c
P_c = Σ_bhw m p_c
Y_c = Σ_bhw m y_c
DiceLoss_c = 1 − (2TP_c + 1)/(P_c + Y_c + 1)
L_baseline = BCE + (0.5/4) Σ_c DiceLoss_c

代码原文：

```python
'''+function+'''
```

## D预声明替换

仅c=2,3（non_flooded_road/flooded_road）替换overlap项：

FP_c = Σ m p_c(1−y_c)
FN_c = Σ m(1−p_c)y_c
TverskyLoss_c = 1 − (TP_c + 0.5)/(TP_c + 0.4 FP_c + 0.6 FN_c + 0.5)
L_D = BCE + (0.5/4) × (DiceLoss_0 + DiceLoss_1 + TverskyLoss_2 + TverskyLoss_3)

alpha=0.4对FP，beta=0.6对FN。道路smoothing=0.5是有意保持与原Dice等价的尺度：当alpha=beta=0.5时，Tversky分子分母乘2精确还原原(2TP+1)/(P+Y+1)。因此没有额外叠加Dice+Tversky，没有改变overlap总系数；空GT处理仍保留，不跳过。

D从同seed重新初始化训练，继承旧sampler而非C。固定40epoch，不进行参数搜索。建筑overlap公式与BCE保持原样；共享参数训练后建筑预测仍可能改变，不能将“建筑loss未变”误称“建筑输出不变”。
'''
    (ROOT/'docs/LOSS_FUNCTION_AUDIT.md').write_text(text,encoding='utf-8')
    print('Loss audit PASSED; C sealed without mutation.')
if __name__=='__main__':main()
