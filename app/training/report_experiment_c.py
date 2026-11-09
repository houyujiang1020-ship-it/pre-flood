"""Build the final C comparison from measured artifacts, without training changes."""
import json,hashlib,sys
from pathlib import Path
import statistics
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'models/experiments/germany-reviewed-gn-class-aware-sampler-20260912'
sys.path.insert(0,str(ROOT/'app/training'))
from positive_sampler import PositiveSampler
CLASSES=['non_flooded_building','flooded_building','non_flooded_road','flooded_road']
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def main():
    e=read(OUT/'evaluation.json');cal=read(OUT/'development-calibration.json');oof=read(OUT/'threshold-oof.json')
    oldoof=read(ROOT/'experiments/diagnostics/germany-reviewed-threshold-oof-20260912.json')
    h=read(OUT/'history.json');manifest=read(OUT/'experiment_manifest.json');assert len(h)==40
    oldh=read(ROOT/'models/experiments/germany-reviewed-gn-sampler-20260912/history.json')
    presence=read(ROOT/'experiments/diagnostics/train-sample-class-presence.json')['tiles']
    tiles=[]
    for x in presence:
        tiles.append({'area':'Germany_Training_Public','label':x['label'],'split':'train','has_flooded_building':x['HAS_FLOODED_BUILDING'],'has_flooded_road':x['HAS_FLOODED_ROAD'],'has_building':x['HAS_NORMAL_BUILDING'] or x['HAS_FLOODED_BUILDING'],'has_road':x['HAS_NORMAL_ROAD'] or x['HAS_FLOODED_ROAD'],'background_only':x['BACKGROUND_ONLY']})
    sampler=PositiveSampler(tiles,manifest['baseline_config']['sampler'],manifest['baseline_config']['seed'])
    oldex=[];labels=['HAS_NORMAL_BUILDING','HAS_FLOODED_BUILDING','HAS_NORMAL_ROAD','HAS_FLOODED_ROAD']
    for epoch in range(40):
        indices,r=sampler.sample(epoch)
        assert r['category_appearances']==oldh[epoch]['sampling']['category_appearances']
        oldex.append({'epoch':epoch+1,'class_sample_exposure_count':{c:sum(presence[i][label] for i in indices) for c,label in zip(CLASSES,labels)},'coverage_fraction':r['coverage_fraction']})
    exposure={'old_sampler_reconstructed_and_checked':oldex,'class_aware':[r['sampling'] for r in h]}
    write(OUT/'sample-exposure-comparison.json',exposure)
    lines=['# Experiment C 对照（2026-09-12）','','## 决定','','**Experiment C 不晋级；保留 germany-reviewed-v1 作为 development 基线，production_ready=false。** C完成40轮，最佳为第40轮；固定阈值、冻结开发阈值、新同集校准与两折OOF均未证明改善。没有运行Experiment D。','','## 可比性','','冻结split SHA256：`'+e['split_sha256']+'`；train98/validation18/test0。审查197项已完成，未重做、未改split。没有读取Louisiana或future blind holdout。','C与旧sampler仅训练配置sampler不同；model_id/output_dir是保存身份变化。网络SiamUnet_diff、GroupNorm8、Adam、LR0.0003、seed20260912、512px、98步×40epoch、增强、0.5选checkpoint均相同。真实baseline已有Dice=0.5，用户明确确认继承；无新增Dice、class weight或Tversky。训练前experiment_manifest.json记录了完整配置和源码哈希。','旧sampler是epoch类别配额；C为6步周期2受淹道路+2受淹建筑+1foreground+1random，周期内打乱、按池打乱索引袋抽取。batch size仍为1，完整周期保证曝光；不声称每个batch能同时包含两个不同标签。最后2步不作完整周期保证。','本实验比较的是两种采样策略整体（比例、次序、池内覆盖），不能再把结果单独归因于其中某一个组成。单seed结果不证明所有class-aware策略无效。weighted仅是历史参考，不属于C的单变量对照。','','## A：统一threshold=0.5','','| 实验 | best epoch | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |','|---|---:|---:|---:|---:|---:|---:|']
    for n,v in e['models'].items():
        m=v['A_threshold_0.5']['metrics'];lines.append('| '+n+' | '+str(v['epoch'])+' | '+' | '.join(f'{m["class_iou"][c]:.6f}' for c in CLASSES)+f' | {m["macro_iou"]:.6f} |')
    lines+=['','## B：原冻结开发阈值0.54/0.45/0.18/0.25','','这些阈值来自旧sampler在Germany validation的校准；统一应用于三种权重，未修改候选阈值。weighted这里并非自身最优校准。所有分数都是开发验证结果。','','| 实验 | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |','|---|---:|---:|---:|---:|---:|']
    for n,v in e['models'].items():
        m=v['B_frozen_development_thresholds']['metrics'];lines.append('| '+n+' | '+' | '.join(f'{m["class_iou"][c]:.6f}' for c in CLASSES)+f' | {m["macro_iou"]:.6f} |')
    lines+=['','## C：新development calibration（不替换冻结阈值）','','仅在相同Germany validation按原0.01网格选择各类最大IoU阈值，得到 '+str(cal['thresholds'])+'。','','| 类别 | IoU | Precision | Recall | F1 |','|---|---:|---:|---:|---:|']
    m=cal['validation']
    for c in CLASSES:lines.append('| '+c+' | '+' | '.join(f'{m[k][c]:.6f}' for k in ['class_iou','class_precision','class_recall','class_f1'])+' |')
    lines+=['',f'新同集校准macro IoU={sum(m["class_iou"].values())/4:.6f}，不是独立精度。受淹道路阈值低至0.04，precision仅约4.06%，恢复召回同时带来大量误报。','','## 同方法两折OOF阈值评价','','沿用原assign_folds与阈值选择代码，每张验证图只使用另一折阈值；已核对C与旧模型两折样本列表完全一致。checkpoint仍由全部18张validation选择，故OOF只涉及阈值，并非完全独立的模型评价。','','| 实验 | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |','|---|---:|---:|---:|---:|---:|']
    for n,v in [('old_sampler',oldoof),('class_aware',oof)]:lines.append('| '+n+' | '+' | '.join(f'{v["class_iou"][c]:.6f}' for c in CLASSES)+f' | {v["macro_iou"]:.6f} |')
    for a,b in zip(oldoof['folds'],oof['folds']):
        assert a['held_labels']==b['held_labels'] and a['calibration_labels']==b['calibration_labels']
    lines+=['','## 实际曝光（每epoch均值）','','旧sampler由原seed与源码重放，40轮的旧category_appearances逐一对上历史；以下普通类别按真实通道重新计数，避免与旧合并has_building/has_road混淆。多标签曝光允许重复计入多个类。','','| 策略 | 普通建筑 | 受淹建筑 | 普通道路 | 受淹道路 | unique coverage |','|---|---:|---:|---:|---:|---:|']
    for n,rs in [('old_sampler',oldex),('class_aware',[r['sampling'] for r in h])]:
        lines.append('| '+n+' | '+' | '.join(f'{statistics.mean(r["class_sample_exposure_count"][c] for r in rs):.2f}' for c in CLASSES)+f' | {statistics.mean(r["coverage_fraction"] for r in rs):.4f} |')
    lines+=['','## 晋级与 Experiment D','','C在冻结阈值下三项重点类别全部下降，两折OOF也全部低于旧sampler；不满足保住受淹建筑和道路的要求，因此不晋级。development candidate继续指向旧sampler第37轮原始权重。','**值得进入D的方案设计，但本轮不运行D。** 概率正负部分重叠、校准后precision仍低，说明只改抽样与阈值没有解决道路空间识别。后续可预声明一个road-aware overlap loss单变量对照，从保留的旧sampler基线出发，先明确它与已有Dice=0.5的替代关系，避免把现有Dice重复叠加。','不能把本结果当作某种新损失必然有效的证据。验证集中仅2张受淹建筑、3张受淹道路；反复使用同一validation有开发过拟合风险，未来blind holdout继续封存，绝不参与调参。','','## 验证与产物','','完整run_tests.ps1退出0：AI9、脚本33、训练26（含新增8项sampler）、Java核心53、HTTP1、Java21 SDK55及注册探针通过。无新增GUI业务验收。','数值污染已修复为0.001282982062548399；来源为旧第37轮history及checkpoint相同指标。完整诊断见ROAD_PROBABILITY_DIAGNOSIS.md。','实验目录保留best_model.pth、last_model.pth、history.json、training_report.json、learning-curves.json、evaluation.json、development-calibration.json、threshold-oof.json、sample-exposure-comparison.json、experiment_manifest.json和completion_manifest.json。','概率诊断目录保留四类全部正/负概率NPZ、100-bin直方图JSON、PR曲线图、threshold表CSV、分位数及数值扫描证据。','模型未部署；candidate_type=development；production_ready=false；本轮blind_holdout_used=false；Louisiana/test均未使用。','','## 复现入口','','使用项目.venv-training Python执行app/training/diagnose_road_probability.py、train_full.py --config config/training.germany-reviewed-gn-class-aware-sampler-20260912.json和evaluate_experiment_c.py。已有训练目录拒绝覆盖；如需复现应另建输出目录，不能覆写冻结产物。render_road_probability.py使用Codex捆绑Python中的matplotlib生成图表；未改变训练依赖。']
    (ROOT/'docs/EXPERIMENT_C_COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    completion={'epochs_completed':40,'best_epoch':40,'promoted':False,'production_ready':False,'blind_holdout_used':False,'louisiana_used':False,'test_used':False,'split_sha256':e['split_sha256'],'decision':'Retain old sampler development candidate. C worse on all three priority classes at frozen thresholds and OOF. D design justified, not executed.','artifact_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='completion_manifest.json'}}
    write(OUT/'completion_manifest.json',completion)
    summary=f'''## 2026-09-12 道路诊断与 Experiment C 已完成（当前状态）

- 人工审查197/197：accepted116/rejected81/pending0；冻结train98/validation18/test0，split未变。
- 原普通道路IoU从history与checkpoint恢复为0.001282982062548399，污染已修复并扫描；正负道路概率部分可分但存在明显重叠，不能仅归为校准问题。
- germany-reviewed-v1已冻结旧sampler第37轮权重及开发阈值0.54/0.45/0.18/0.25，candidate_type=development，production_ready=false。
- C仅改sampler，用户确认继承已有Dice=0.5；40轮完成，最佳第40轮。固定0.5 macro={e['models']['class_aware']['A_threshold_0.5']['metrics']['macro_iou']:.6f}；原冻结阈值macro={e['models']['class_aware']['B_frozen_development_thresholds']['metrics']['macro_iou']:.6f}；新同集开发校准macro={sum(cal['validation']['class_iou'].values())/4:.6f}；两折OOF macro={oof['macro_iou']:.6f}。
- 三项重点类别在冻结阈值及OOF下均退步，C不晋级、未部署。D仅建议设计road-aware overlap loss单变量对照，本轮没有运行D、没有增加epoch。
- 完整回归通过：AI9、脚本33、训练26、Java核心53、HTTP1、SDK55与注册探针。
- 本轮没有读取Louisiana、test或future blind holdout。OOF仅把阈值选择折外化，不是独立模型精度。
- 报告：docs/ROAD_PROBABILITY_DIAGNOSIS.md、docs/EXPERIMENT_C_COMPARISON.md。实验目录：models/experiments/germany-reviewed-gn-class-aware-sampler-20260912。无运行中训练任务。

'''
    for filename in ['PROJECT_STATUS.md','NEXT_TASK.md']:
        p=ROOT/filename;s=p.read_text(encoding='utf-8')
        marker='# 当前任务：道路诊断与 Experiment C（2026-09-12）'
        if s.startswith(marker):s=s[s.index('\n\n',s.index('最终结果以'))+2:]
        extra='下一步：保留旧development基线。可制定Experiment D方案，明确与已有Dice的关系及晋级标准后再实验；不要重做审查、改split或读取blind holdout。以下内容仅为历史。\n\n' if filename=='NEXT_TASK.md' else '以下较早日期记录仅为历史；以本节为准。\n\n'
        p.write_text(summary+extra+s,encoding='utf-8')
    p=ROOT/'docs/DEVLOG.md';p.write_text(p.read_text(encoding='utf-8')+'\n'+summary,encoding='utf-8')
    print(json.dumps({'A':e['models']['class_aware']['A_threshold_0.5']['metrics']['macro_iou'],'B':e['models']['class_aware']['B_frozen_development_thresholds']['metrics']['macro_iou'],'C':sum(cal['validation']['class_iou'].values())/4,'OOF':oof['macro_iou']}))
if __name__=='__main__':main()
