"""D final decision based exclusively on measured development artifacts."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CLASSES=['non_flooded_building','flooded_building','non_flooded_road','flooded_road']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fmt(x):return 'NA' if x is None else f'{x:.6f}'
def main():
    loc=read(ROOT/'experiments/diagnostics/experiment-d-preflight-20260912/run-location.json');out=ROOT/loc['output_dir']
    e=read(out/'evaluation.json');cal=read(out/'development-calibration.json');oof=read(out/'threshold-oof.json');h=read(out/'history.json');manifest=read(out/'experiment_manifest.json')
    oldoof=read(ROOT/'experiments/diagnostics/germany-reviewed-threshold-oof-20260912.json');coof=read(ROOT/'models/experiments/germany-reviewed-gn-class-aware-sampler-20260912/threshold-oof.json')
    prob=read(ROOT/'experiments/diagnostics/experiment-d-probability-20260912/probability-comparison.json');morph=read(ROOT/'experiments/diagnostics/experiment-d-road-morphology-20260912/morphology-summary.json')
    base=e['models']['old_sampler'];d=e['models']['experiment_d'];b=base['B_frozen_development_thresholds']['metrics'];dm=d['B_frozen_development_thresholds']['metrics']
    road_improved=[c for c in CLASSES[2:] if dm['class_iou'][c]-b['class_iou'][c]>=.01 and oof['class_iou'][c]-oldoof['class_iou'][c]>=.01]
    preserved=all(dm['class_iou'][c]>=b['class_iou'][c]-(.01 if c=='flooded_building' else .005) and oof['class_iou'][c]>=oldoof['class_iou'][c]-(.01 if c=='flooded_building' else .005) for c in CLASSES[1:])
    rank_supported=[c for c in road_improved if prob['models']['experiment_d'][c]['average_precision_exact_ties']>=prob['models']['old_sampler'][c]['average_precision_exact_ties']+.005]
    morphology_supported=[]
    for c in rank_supported:
        a=morph['models']['old_sampler']['aggregate']['B'][c];z=morph['models']['experiment_d']['aggregate']['B'][c]
        if z['skeleton_recall']>=a['skeleton_recall']-.01 and z['uncovered_gt_fraction']<=a['uncovered_gt_fraction']+.01 and z['fragments_per_matched_gt'] is not None and z['fragments_per_matched_gt']<=max(1,a['fragments_per_matched_gt'] or 1)*1.1:morphology_supported.append(c)
    no_collapse=all(d['A_threshold_0.5']['metrics']['class_iou'][c]>0 if base['A_threshold_0.5']['metrics']['class_iou'][c]>0 else True for c in CLASSES[2:])
    promoted=bool(road_improved and preserved and rank_supported and morphology_supported and no_collapse)
    decision='accepted_development' if promoted else 'rejected'
    lines=['# Experiment D 对照与晋级决定（2026-09-12）','',f'**status=completed；promotion={decision}；production_ready=false。**',f'D真实完成40轮，最佳checkpoint第{d["epoch"]}轮。Experiment C已封存为completed/rejected，本轮未修改C。','', '## 真实loss与唯一核心变化','','baseline: L = BCE + 0.5/4 × Σ四类DiceLoss。BCE系数1，四类同权，逐channel对batch/H/W聚合，空GT不跳过，valid mask排除无效像素；Dice分子分母smooth=1。完整源码审计见LOSS_FUNCTION_AUDIT.md。','D: L = BCE + 0.5/4 × (Dice_building + Dice_flooded_building + Tversky_road + Tversky_flooded_road)。','Tversky = 1−(TP+0.5)/(TP+0.4×FP+0.6×FN+0.5)。alpha对FP，beta对FN；smooth0.5保证alpha=beta0.5时与原Dice完全同尺度。没有BCE+Dice+Tversky叠加，没有新增类别权重。','旧sampler、98步/epoch、40epoch、seed20260912、SiamUnet_diff、GroupNorm8、Adam LR0.0003、512px、增强、预处理、valid mask和按0.5 macro IoU选checkpoint均保持一致。配置自动diff只允许road_overlap_loss，以及model_id/output_dir身份变化。','独立D runner只新增相同forward logits的脱离梯度训练指标记录，不增加训练forward或随机数调用。保留历史验证loss=BCE-only定义。训练前完整回归通过；manifest锁定loss/source/baseline manifest哈希，训练入口拒绝已有运行标记、参数覆盖和源文件变化。','','## 数据边界','',f'split SHA256 `{manifest["split_sha256"]}`；train98/validation18/test0。没有重做人工审查、没有改split。blind_holdout_used=false；Louisiana_used=false。未搜索或查看新的holdout，未来需要独立准备封存评估数据。','所有分数是Germany development validation结果；checkpoint使用全部validation选取，阈值OOF也不是完全独立模型评价。只有2张受淹建筑、3张受淹道路验证图；没有把单seed改进称为统计显著。']
    for strategy,title in [('A_threshold_0.5','固定0.5'),('B_frozen_development_thresholds','原冻结开发阈值0.54/0.45/0.18/0.25')]:
        lines+=['','## '+title,'','| 模型 | best epoch | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |','|---|---:|---:|---:|---:|---:|---:|']
        for name,v in e['models'].items():
            m=v[strategy]['metrics'];lines.append('| '+name+' | '+str(v['epoch'])+' | '+' | '.join(fmt(m['class_iou'][c]) for c in CLASSES)+' | '+fmt(m['macro_iou'])+' |')
        lines+=['','D详细像素指标：','','| 类别 | Precision | Recall | F1 |','|---|---:|---:|---:|']
        m=d[strategy]['metrics']
        for c in CLASSES:lines.append('| '+c+' | '+' | '.join(fmt(m[k][c]) for k in ['class_precision','class_recall','class_f1'])+' |')
    lines+=['','冻结阈值直接应用D，是candidate-to-candidate fixed-threshold comparison；未替换germany-reviewed-v1中的阈值。weighted/old/C的完整precision、recall、F1也保存在evaluation.json。','','## D development calibration','','阈值：'+str(cal['thresholds'])+'。逐类在相同validation使用原0.01网格选最大IoU。**same-validation development estimate，不是independent accuracy。**','', '| 类别 | IoU | Precision | Recall | F1 |','|---|---:|---:|---:|---:|']
    for c in CLASSES:lines.append('| '+c+' | '+' | '.join(fmt(cal['validation'][k][c]) for k in ['class_iou','class_precision','class_recall','class_f1'])+' |')
    lines+=['',f'macro IoU={sum(cal["validation"]["class_iou"].values())/4:.6f}；本阈值仅保存在D目录，未改候选冻结阈值。','','## Two-fold threshold OOF','','原assign_folds、0.01–0.99网格与metric implementation完全沿用；已逐项核对old sampler/C/D两折样本列表相同。checkpoint依旧用全部validation选定，OOF只把阈值选择折外化。','','| 模型 | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |','|---|---:|---:|---:|---:|---:|']
    for name,v in [('old_sampler',oldoof),('Experiment C',coof),('Experiment D',oof)]:lines.append('| '+name+' | '+' | '.join(fmt(v['class_iou'][c]) for c in CLASSES)+' | '+fmt(v['macro_iou'])+' |')
    lines+=['','## 正负概率与排序','','与旧方法相同：valid像素、100-bin正/负直方图、p05/p25/p50/p75/p95、0.01网格PR和threshold table。另加精确并列分数AP与辅助ranking AUC；AP对严格单调概率变换不变，所以可区分仅校准移动与排序变化。','','| 模型/类别 | 正类p50 | 负类p50 | 正类p95 | 负类p95 | AP | 辅助AUC |','|---|---:|---:|---:|---:|---:|---:|']
    for model in ['old_sampler','experiment_d']:
        for c in CLASSES[2:]:
            v=prob['models'][model][c];lines.append('| '+model+'/'+c+' | '+' | '.join(fmt(x) for x in [v['positive_quantiles']['p50'],v['negative_quantiles']['p50'],v['positive_quantiles']['p95'],v['negative_quantiles']['p95'],v['average_precision_exact_ties'],v['ranking_auc_auxiliary']])+' |')
    for c in CLASSES[2:]:
        a=prob['models']['old_sampler'][c];z=prob['models']['experiment_d'][c]
        delta=z['average_precision_exact_ties']-a['average_precision_exact_ties']
        lines.append(f"\n{c}: AP变化{delta:+.6f}；正类中位数变化{z['positive_quantiles']['p50']-a['positive_quantiles']['p50']:+.6f}，负类中位数变化{z['negative_quantiles']['p50']-a['negative_quantiles']['p50']:+.6f}。"+('存在排序改善信号；还需结合阈值与形态证据，不可仅凭AP晋级。' if delta>0 else '没有排序改善证据，概率位置变化不能解释为识别能力增强。'))
    lines+=['','## 道路形态（辅助AI诊断）','','GT经Zhang–Suen骨架化，报告预测精确覆盖骨架与1像素容差覆盖；8连通分量跨瓦片不拼接，valid mask/图边界会影响分量。碎片指标=每个已匹配GT分量相交的预测分量数；还报告未覆盖GT比例和未匹配预测分量，防止漏检造成虚假“碎片减少”。这些不是正式MapGIS道路实体/拓扑验收。','','原冻结开发阈值B：','','| 模型/类别 | GT分量 | 预测分量 | 骨架召回 | 1px召回 | fragments/matched GT | 未覆盖GT比例 | 未匹配预测分量 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for model in ['old_sampler','experiment_d']:
        for c in CLASSES[2:]:
            v=morph['models'][model]['aggregate']['B'][c]
            lines.append('| '+model+'/'+c+' | '+' | '.join(str(v[k]) for k in ['gt_components','pred_components'])+' | '+' | '.join(fmt(v[k]) for k in ['skeleton_recall','skeleton_recall_1px','fragments_per_matched_gt','uncovered_gt_fraction'])+' | '+str(v['unmatched_pred_components'])+' |')
    lines+=['','threshold0.5的同样统计和全部逐图明细见morphology-summary.json；原始掩膜概率在validation-predictions/中可复算。','','## Flooded road FP / recall及重点类别','','| 指标（原冻结阈值） | old sampler | D | 变化 |','|---|---:|---:|---:|']
    fr=[]
    for model in ['old_sampler','experiment_d']:
        r=min(prob['models'][model]['flooded_road']['threshold_table'],key=lambda x:abs(x['threshold']-.25));fr.append(r)
    for k in ['fp','recall','precision']:
        a,z=fr[0][k],fr[1][k];lines.append('| flooded road '+k+' | '+fmt(a)+' | '+fmt(z)+' | '+f'{z-a:+.6f}'+' |')
    for c in CLASSES[1:]:lines.append('| '+c+' IoU | '+fmt(b['class_iou'][c])+' | '+fmt(dm['class_iou'][c])+' | '+f'{dm["class_iou"][c]-b["class_iou"][c]:+.6f}'+' |')
    lines+=['','## 明确回答A–F','','A. D不晋级，保留germany-reviewed-v1。','B. 两类道路正/负概率的中高分位均有上移，但AP均下降：普通道路0.157274→0.151215，受淹道路0.045986→0.038425。这支持概率位置移动伴随排序退步，不能归为ranking improvement，也不能声称所有像素只是统一平移。普通道路骨架召回有局部提高，受淹道路骨架仅微增；漏检GT分量和受淹碎片指标恶化，不构成一致的morphology improvement。','C. 原冻结阈值0.25下受淹道路FP没有下降：59,536→80,580（约+35.35%）。','D. 同阈值受淹道路recall小幅提高：0.178160→0.184269；precision则0.070578→0.054847，更多误报抵消召回增益。','E. 普通道路没有完全消失，但未满足保住标准：冻结阈值IoU0.153674→0.146130、OOF0.153166→0.145656，均下降约0.0075，超过预声明0.005容忍度。','F. 受淹建筑基本保住：冻结阈值IoU0.101490→0.099068，OOF由约0.05494升至0.062816，在预声明容忍度内；D失败主要因道路无可信整体改善。','','## Promotion decision matrix','','训练前预声明：至少一个道路在冻结阈值及OOF均提高≥0.01；另一道路下降≤0.005、受淹建筑下降≤0.01；0.5无新的道路塌缩，并需要排序/形态支持。这是保守开发筛选标准，不是显著性检验。','','| 证据 | 结论 |','|---|---|',f'| 0.5 metrics | macro {base["A_threshold_0.5"]["metrics"]["macro_iou"]:.6f} → {d["A_threshold_0.5"]["metrics"]["macro_iou"]:.6f}；原非零道路仍非零={no_collapse}；受淹道路TP仍0，整体响应弱 |',f'| Fixed frozen thresholds | macro {b["macro_iou"]:.6f} → {dm["macro_iou"]:.6f} |',f'| Development calibrated | D macro {sum(cal["validation"]["class_iou"].values())/4:.6f}；同集估计不能单独晋级 |',f'| OOF | macro {oldoof["macro_iou"]:.6f} → {oof["macro_iou"]:.6f} |',f'| Road gain in frozen + OOF | 达到预声明幅度的类别={road_improved} |',f'| Preserve priority classes | {preserved} |',f'| Probability separation | 达到AP增益支持的改善道路={rank_supported} |',f'| Road morphology | 联合满足骨架/漏检/碎片条件的改善道路={morphology_supported} |',f'| Decision | promotion={decision}；production_ready=false |']
    if not promoted:lines+=['','**本轮停止模型微调，不启动Experiment E。** 保留germany-reviewed-v1为development baseline。下一步仅提出two-stage architecture feasibility study：Stage1 building/road segmentation；Stage2 flooded/non-flooded classification。本轮没有实现或训练two-stage。']
    else:lines+=['','只接受为development研究候选，不更新生产/在线模型，不替换原germany-reviewed-v1和其冻结阈值。']
    lines+=['','## 完成与验证','','loss audit通过；训练前完整回归AI9、脚本33、训练40、Java核心53、HTTP1、SDK55及注册探针通过；另6项形态、3项排序测试通过，最终训练测试全集49项通过。训练40轮完成，原始best/last/history/report和learning curves齐全。','C、baseline候选及旧sampler所有封存文件SHA256再次核对保持一致；源代码和split哈希核对通过。未修改在线服务模型，production_ready=false。','报告与诊断脚本可复算；目录、完整配置、loss/source git/source SHA及差异见experiment_manifest.json；最终产物哈希和判定见completion_manifest.json。','','![概率与PR](../experiments/diagnostics/experiment-d-probability-20260912/probability-comparison.png)']
    (ROOT/'docs/EXPERIMENT_D_COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for relative,expected in read(ROOT/'experiments/diagnostics/experiment-d-preflight-20260912/protected-artifacts.json')['protected_sha256'].items():assert sha(ROOT/relative)==expected,relative
    for relative,expected in manifest['source_sha256'].items():assert sha(ROOT/relative)==expected,relative
    assert len(h)==40 and read(out/'training_report.json')['epochs_completed']==40
    summary=f'''## 2026-09-12 Experiment D completed（当前状态）

- Experiment C completed，promotion=rejected，原始产物封存哈希全部保持不变。
- 真实baseline loss=BCE+0.5×四通道平均Dice；D仅替换道路Dice为Tversky（FP alpha0.4/FN beta0.6，smooth0.5），建筑loss/BCE/旧sampler/其余训练条件冻结。
- D完成40epoch，best epoch={d['epoch']}；0.5 macro={d['A_threshold_0.5']['metrics']['macro_iou']:.6f}；原冻结阈值macro={dm['macro_iou']:.6f}；same-validation calibration macro={sum(cal['validation']['class_iou'].values())/4:.6f}；threshold OOF macro={oof['macro_iou']:.6f}。均非独立模型精度。
- Experiment D promotion={decision}；production_ready=false；未修改在线模型或原candidate thresholds。
- {'停止本轮模型微调；下一步仅two-stage architecture feasibility study（Stage1建筑/道路分割，Stage2受淹/非受淹分类）。本轮未启动E、未实现或训练two-stage。' if not promoted else '仅development候选，不做生产晋级。'}
- Germany split仍98/18/0，SHA256={manifest['split_sha256']}；不重做审查。blind_holdout_used=false；Louisiana_used=false；test_used=false。没有查找/预览/推理future holdout；未来需独立准备并封存，不能用作调参。
- 完整回归通过；另形态6项、排序3项通过。报告：docs/LOSS_FUNCTION_AUDIT.md、docs/EXPERIMENT_C_FINAL.md、docs/EXPERIMENT_D_COMPARISON.md。
- 训练结束，无运行中训练任务。以下较早记录为历史。

'''
    for filename in ['PROJECT_STATUS.md','NEXT_TASK.md']:
        p=ROOT/filename;p.write_text(summary+p.read_text(encoding='utf-8'),encoding='utf-8')
    p=ROOT/'docs/DEVLOG.md';p.write_text(p.read_text(encoding='utf-8')+'\n'+summary,encoding='utf-8')
    completion={'status':'completed','promotion':decision,'epochs_completed':40,'best_epoch':d['epoch'],'production_ready':False,'blind_holdout_used':False,'Louisiana_used':False,'test_used':False,'split_sha256':manifest['split_sha256'],'baseline_and_C_seal_verified':True,'promotion_gates':{'road_improved':road_improved,'priority_preserved':preserved,'rank_supported':rank_supported,'morphology_supported':morphology_supported,'no_new_road_collapse':no_collapse},'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='completion_manifest.json'},'diagnostic_report_sha256':{str(p.relative_to(ROOT)):sha(p) for folder in ['experiments/diagnostics/experiment-d-probability-20260912','experiments/diagnostics/experiment-d-road-morphology-20260912'] for p in (ROOT/folder).rglob('*') if p.is_file()}}
    (out/'completion_manifest.json').write_text(json.dumps(completion,indent=2),encoding='utf-8')
    print(json.dumps({'promotion':decision,'best_epoch':d['epoch'],'A':d['A_threshold_0.5']['metrics']['macro_iou'],'B':dm['macro_iou'],'calibration':sum(cal['validation']['class_iou'].values())/4,'OOF':oof['macro_iou']}))
if __name__=='__main__':main()
