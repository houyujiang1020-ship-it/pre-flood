"""Render reproducible probability figures and a diagnosis from saved statistics."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'experiments/diagnostics/road-probability-20260912'
d=json.loads((out/'probability-diagnosis.json').read_text())
fig,axes=plt.subplots(4,2,figsize=(12,15),layout='constrained')
for i,(name,v) in enumerate(d['classes'].items()):
    edges=np.array(v['histogram_edges']);centers=(edges[:-1]+edges[1:])/2
    ax=axes[i,0]
    for kind,color in [('positive','#de6237'),('negative','#3166a1')]:
        y=np.array(v[kind+'_histogram'])/v[kind+'_count']
        ax.stairs(y,edges,label='GT '+kind,color=color,linewidth=1.6)
    ax.set(yscale='log',ylim=(1e-6,1),xlim=(0,1),xlabel='Predicted probability',ylabel='Fraction within GT group (log)',title=name)
    ax.legend();ax.grid(alpha=.15)
    ax=axes[i,1];rows=v['threshold_table']
    ax.plot([r['recall'] for r in rows],[r['precision'] for r in rows],color='#3166a1')
    ax.axhline(v['prevalence'],linestyle='--',color='gray',label='Prevalence')
    for threshold,color in [(0.5,'#de6237'),([.54,.45,.18,.25][i],'#2a8958')]:
        r=min(rows,key=lambda r:abs(r['threshold']-threshold))
        ax.scatter(r['recall'],r['precision'],color=color,zorder=4)
        ax.annotate(f"t={threshold}",(r['recall'],r['precision']),xytext=(8,12 if threshold==0.5 else -20),textcoords='offset points')
    ax.set(xlim=(0,1),ylim=(0,1),xlabel='Recall',ylabel='Precision',title='PR curve (threshold grid 0.01)');ax.grid(alpha=.15);ax.legend()
fig.suptitle('Germany development validation | 18 tiles | Valid pixels only\nBaseline epoch 37; checkpoint selection and calibration are not independent evaluation',fontsize=12)
fig.savefig(out/'probability-histograms-pr.png',dpi=160)
fig.savefig(out/'probability-histograms-pr.pdf')
lines=['# 道路概率诊断（2026-09-12）','','仅使用冻结 Germany validation 18 张的有效监督像素。当前 sampler checkpoint 第37轮。没有使用 Louisiana、test 或 future blind holdout。本轮不重复人工审查，不改变 split。','','## 概率分布','','正负分布均按各自像素总数归一化；直方图使用对数纵轴，避免大量背景掩盖正类。PR 曲线采用 0.01 阈值网格，CSV保留 TP、FP、precision、recall、IoU；NPZ保存全部有效正负像素概率。','','| 类别 | GT组 | p05 | p25 | p50 | p75 | p95 |','|---|---|---:|---:|---:|---:|---:|']
for name,v in d['classes'].items():
    for kind in ['positive','negative']:
        lines.append('| '+name+' | '+kind+' | '+' | '.join(f'{x:.6f}' for x in v[kind+'_quantiles'].values())+' |')
lines+=['','## 阈值与响应','','| 类别 | 阈值 | Precision | Recall | IoU |','|---|---:|---:|---:|---:|']
for i,(name,v) in enumerate(d['classes'].items()):
    for th in [.5,[.54,.45,.18,.25][i]]:
        r=min(v['threshold_table'],key=lambda x:abs(x['threshold']-th))
        lines.append(f"| {name} | {th:.2f} | {r['precision']:.6f} | {r['recall']:.6f} | {r['iou']:.6f} |")
lines+=['','## 解释','','1. 普通道路正类概率整体偏低，但相对负类有区分信号：正类中位数0.1122，负类0.0076。然而负类p95=0.1230已超过正类中位数，重叠不可忽视。','2. 受淹道路不能归因为“只是 calibration 偏低”：正类中位数0.0801，负类p95=0.0881；正类p25=0.0213，负类长尾也覆盖该范围。阈值无法消除排序/空间识别错误。','3. 两类道路不是完全不可分，也不是充分分离；大量负像素即使只有较小比例进入高概率尾部，也会形成大量FP。PR与IoU比单独ROC更能揭示当前少数类问题。','4. 0.5高于两类道路正类p95，绝大多数真正道路被判负，受淹道路在该阈值TP为0。','5. 0.18/0.25把部分正类中高概率尾部纳入预测，恢复召回，同时也增加FP；恢复响应不等于可靠分类。旧同集校准IoU仅0.15367/0.05324，折外阈值IoU0.15317/0.02468，仍明显不足。','','## 旧 sampler 审计','','旧实现是 overlapping category quotas，不是任意正类共享一个池。受淹建筑和受淹道路至少各ceil(98×0.4)=40次，建筑/道路（含受淹）至少各59次，背景最多9次；满足配额后随机补足，再对整个epoch打乱。有放回，重叠样本对多个配额计数。','真实训练类别：普通建筑61、受淹建筑21、普通道路92、受淹道路28、纯背景0。一个样本可多标签。旧has_building=68/has_road=95是包含受淹类别的合并语义。','新 sampler 保持batch size1，每6个连续步骤由受淹道路2、受淹建筑2、foreground1、random1组成，周期内打乱，每池用打乱的索引袋循环取样；缺失类别显式回退random并记录。因为batch size1，不能保证每个batch同时含两个不相交类别；完整6步周期保证两类曝光。最后不足6步的尾部不作此保证。','','## 数值修复与边界','','原污染单元格已从 history.json 第37轮与 best_model.pth 的 history 一致恢复为 **0.001282982062548399**；独立道路诊断使用计数除法给出0.0012829820879787562，末位差来自浮点精度。修复来源及Markdown/JSON扫描清单见numeric-repair-audit.json。','此前“以概率校准问题为主”的表述过强，修订为概率整体偏低并伴随正负重叠。OOF只把阈值选择折外化，checkpoint仍由全部validation选择，不能称独立模型精度。','candidate_type=development；production_ready=false；冻结开发阈值0.54/0.45/0.18/0.25仅属于Germany development validation。','','![概率分布与PR曲线](../experiments/diagnostics/road-probability-20260912/probability-histograms-pr.png)']
(ROOT/'docs/ROAD_PROBABILITY_DIAGNOSIS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
p=ROOT/'docs/GERMANY_REVIEWED_TRAINING_COMPARISON_20260912.md'
s=p.read_text(encoding='utf-8').replace('该结果说明当前道路失败以概率校准问题为主，而不是标签完全缺失；','该结果说明降低阈值能够恢复部分道路响应，标签并非完全缺失；正负概率仍有重叠，不能断言只是校准问题（见 ROAD_PROBABILITY_DIAGNOSIS.md）；')
p.write_text(s,encoding='utf-8')
print('Rendered histogram/PR figures and diagnosis.')
