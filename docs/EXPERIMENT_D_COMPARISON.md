# Experiment D 对照与晋级决定（2026-09-12）

**status=completed；promotion=rejected；production_ready=false。**
D真实完成40轮，最佳checkpoint第38轮。Experiment C已封存为completed/rejected，本轮未修改C。

## 真实loss与唯一核心变化

baseline: L = BCE + 0.5/4 × Σ四类DiceLoss。BCE系数1，四类同权，逐channel对batch/H/W聚合，空GT不跳过，valid mask排除无效像素；Dice分子分母smooth=1。完整源码审计见LOSS_FUNCTION_AUDIT.md。
D: L = BCE + 0.5/4 × (Dice_building + Dice_flooded_building + Tversky_road + Tversky_flooded_road)。
Tversky = 1−(TP+0.5)/(TP+0.4×FP+0.6×FN+0.5)。alpha对FP，beta对FN；smooth0.5保证alpha=beta0.5时与原Dice完全同尺度。没有BCE+Dice+Tversky叠加，没有新增类别权重。
旧sampler、98步/epoch、40epoch、seed20260912、SiamUnet_diff、GroupNorm8、Adam LR0.0003、512px、增强、预处理、valid mask和按0.5 macro IoU选checkpoint均保持一致。配置自动diff只允许road_overlap_loss，以及model_id/output_dir身份变化。
独立D runner只新增相同forward logits的脱离梯度训练指标记录，不增加训练forward或随机数调用。保留历史验证loss=BCE-only定义。训练前完整回归通过；manifest锁定loss/source/baseline manifest哈希，训练入口拒绝已有运行标记、参数覆盖和源文件变化。

## 数据边界

split SHA256 `14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1`；train98/validation18/test0。没有重做人工审查、没有改split。blind_holdout_used=false；Louisiana_used=false。未搜索或查看新的holdout，未来需要独立准备封存评估数据。
所有分数是Germany development validation结果；checkpoint使用全部validation选取，阈值OOF也不是完全独立模型评价。只有2张受淹建筑、3张受淹道路验证图；没有把单seed改进称为统计显著。

## 固定0.5

| 模型 | best epoch | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |
|---|---:|---:|---:|---:|---:|---:|
| weighted | 19 | 0.196683 | 0.001032 | 0.113490 | 0.000000 | 0.077801 |
| old_sampler | 37 | 0.226175 | 0.100068 | 0.001283 | 0.000000 | 0.081882 |
| class_aware | 40 | 0.216022 | 0.073605 | 0.000050 | 0.000000 | 0.072419 |
| experiment_d | 38 | 0.227226 | 0.096127 | 0.000519 | 0.000000 | 0.080968 |

D详细像素指标：

| 类别 | Precision | Recall | F1 |
|---|---:|---:|---:|
| non_flooded_building | 0.306933 | 0.466665 | 0.370308 |
| flooded_building | 0.124782 | 0.295074 | 0.175393 |
| non_flooded_road | 0.150725 | 0.000520 | 0.001037 |
| flooded_road | NA | 0.000000 | 0.000000 |

## 原冻结开发阈值0.54/0.45/0.18/0.25

| 模型 | best epoch | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |
|---|---:|---:|---:|---:|---:|---:|
| weighted | 19 | 0.197908 | 0.010192 | 0.125178 | 0.016502 | 0.087445 |
| old_sampler | 37 | 0.227066 | 0.101490 | 0.153674 | 0.053243 | 0.133868 |
| class_aware | 40 | 0.182863 | 0.074415 | 0.139946 | 0.030859 | 0.107021 |
| experiment_d | 38 | 0.221385 | 0.099068 | 0.146130 | 0.044132 | 0.127678 |

D详细像素指标：

| 类别 | Precision | Recall | F1 |
|---|---:|---:|---:|
| non_flooded_building | 0.330128 | 0.401946 | 0.362514 |
| flooded_building | 0.118090 | 0.380810 | 0.180276 |
| non_flooded_road | 0.180066 | 0.436738 | 0.254997 |
| flooded_road | 0.054847 | 0.184269 | 0.084533 |

冻结阈值直接应用D，是candidate-to-candidate fixed-threshold comparison；未替换germany-reviewed-v1中的阈值。weighted/old/C的完整precision、recall、F1也保存在evaluation.json。

## D development calibration

阈值：{'non_flooded_building': 0.5, 'flooded_building': 0.44, 'non_flooded_road': 0.22, 'flooded_road': 0.24}。逐类在相同validation使用原0.01网格选最大IoU。**same-validation development estimate，不是independent accuracy。**

| 类别 | IoU | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| non_flooded_building | 0.227226 | 0.306933 | 0.466665 | 0.370308 |
| flooded_building | 0.099171 | 0.116798 | 0.396534 | 0.180446 |
| non_flooded_road | 0.148451 | 0.195272 | 0.382386 | 0.258524 |
| flooded_road | 0.044161 | 0.053760 | 0.198298 | 0.084587 |

macro IoU=0.129752；本阈值仅保存在D目录，未改候选冻结阈值。

## Two-fold threshold OOF

原assign_folds、0.01–0.99网格与metric implementation完全沿用；已逐项核对old sampler/C/D两折样本列表相同。checkpoint依旧用全部validation选定，OOF只把阈值选择折外化。

| 模型 | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |
|---|---:|---:|---:|---:|---:|
| old_sampler | 0.223417 | 0.054944 | 0.153166 | 0.024676 | 0.114051 |
| Experiment C | 0.224587 | 0.029982 | 0.144371 | 0.016738 | 0.103920 |
| Experiment D | 0.221473 | 0.062816 | 0.145656 | 0.027891 | 0.114459 |

## 正负概率与排序

与旧方法相同：valid像素、100-bin正/负直方图、p05/p25/p50/p75/p95、0.01网格PR和threshold table。另加精确并列分数AP与辅助ranking AUC；AP对严格单调概率变换不变，所以可区分仅校准移动与排序变化。

| 模型/类别 | 正类p50 | 负类p50 | 正类p95 | 负类p95 | AP | 辅助AUC |
|---|---:|---:|---:|---:|---:|---:|
| old_sampler/non_flooded_road | 0.112185 | 0.007644 | 0.417486 | 0.123010 | 0.157274 | 0.858237 |
| old_sampler/flooded_road | 0.080095 | 0.002902 | 0.349206 | 0.088080 | 0.045986 | 0.861211 |
| experiment_d/non_flooded_road | 0.138220 | 0.008746 | 0.438801 | 0.155178 | 0.151215 | 0.857902 |
| experiment_d/flooded_road | 0.093628 | 0.003140 | 0.354769 | 0.113497 | 0.038425 | 0.849342 |

non_flooded_road: AP变化-0.006059；正类中位数变化+0.026035，负类中位数变化+0.001102。没有排序改善证据，概率位置变化不能解释为识别能力增强。

flooded_road: AP变化-0.007561；正类中位数变化+0.013534，负类中位数变化+0.000238。没有排序改善证据，概率位置变化不能解释为识别能力增强。

## 道路形态（辅助AI诊断）

GT经Zhang–Suen骨架化，报告预测精确覆盖骨架与1像素容差覆盖；8连通分量跨瓦片不拼接，valid mask/图边界会影响分量。碎片指标=每个已匹配GT分量相交的预测分量数；还报告未覆盖GT比例和未匹配预测分量，防止漏检造成虚假“碎片减少”。这些不是正式MapGIS道路实体/拓扑验收。

原冻结开发阈值B：

| 模型/类别 | GT分量 | 预测分量 | 骨架召回 | 1px召回 | fragments/matched GT | 未覆盖GT比例 | 未匹配预测分量 |
|---|---:|---:|---:|---:|---:|---:|---:|
| old_sampler/non_flooded_road | 30 | 1324 | 0.488798 | 0.553133 | 5.066667 | 0.000000 | 1175 |
| old_sampler/flooded_road | 8 | 1171 | 0.228001 | 0.307529 | 8.500000 | 0.000000 | 1103 |
| experiment_d/non_flooded_road | 30 | 1247 | 0.527787 | 0.579416 | 4.827586 | 0.033333 | 1111 |
| experiment_d/flooded_road | 8 | 1046 | 0.231932 | 0.310856 | 9.428571 | 0.125000 | 980 |

threshold0.5的同样统计和全部逐图明细见morphology-summary.json；原始掩膜概率在validation-predictions/中可复算。

## Flooded road FP / recall及重点类别

| 指标（原冻结阈值） | old sampler | D | 变化 |
|---|---:|---:|---:|
| flooded road fp | 59536.000000 | 80580.000000 | +21044.000000 |
| flooded road recall | 0.178160 | 0.184269 | +0.006108 |
| flooded road precision | 0.070578 | 0.054847 | -0.015731 |
| flooded_building IoU | 0.101490 | 0.099068 | -0.002422 |
| non_flooded_road IoU | 0.153674 | 0.146130 | -0.007544 |
| flooded_road IoU | 0.053243 | 0.044132 | -0.009112 |

## 明确回答A–F

A. D不晋级，保留germany-reviewed-v1。
B. 两类道路正/负概率的中高分位均有上移，但AP均下降：普通道路0.157274→0.151215，受淹道路0.045986→0.038425。这支持概率位置移动伴随排序退步，不能归为ranking improvement，也不能声称所有像素只是统一平移。普通道路骨架召回有局部提高，受淹道路骨架仅微增；漏检GT分量和受淹碎片指标恶化，不构成一致的morphology improvement。
C. 原冻结阈值0.25下受淹道路FP没有下降：59,536→80,580（约+35.35%）。
D. 同阈值受淹道路recall小幅提高：0.178160→0.184269；precision则0.070578→0.054847，更多误报抵消召回增益。
E. 普通道路没有完全消失，但未满足保住标准：冻结阈值IoU0.153674→0.146130、OOF0.153166→0.145656，均下降约0.0075，超过预声明0.005容忍度。
F. 受淹建筑基本保住：冻结阈值IoU0.101490→0.099068，OOF由约0.05494升至0.062816，在预声明容忍度内；D失败主要因道路无可信整体改善。

## Promotion decision matrix

训练前预声明：至少一个道路在冻结阈值及OOF均提高≥0.01；另一道路下降≤0.005、受淹建筑下降≤0.01；0.5无新的道路塌缩，并需要排序/形态支持。这是保守开发筛选标准，不是显著性检验。

| 证据 | 结论 |
|---|---|
| 0.5 metrics | macro 0.081882 → 0.080968；原非零道路仍非零=True；受淹道路TP仍0，整体响应弱 |
| Fixed frozen thresholds | macro 0.133868 → 0.127678 |
| Development calibrated | D macro 0.129752；同集估计不能单独晋级 |
| OOF | macro 0.114051 → 0.114459 |
| Road gain in frozen + OOF | 达到预声明幅度的类别=[] |
| Preserve priority classes | False |
| Probability separation | 达到AP增益支持的改善道路=[] |
| Road morphology | 联合满足骨架/漏检/碎片条件的改善道路=[] |
| Decision | promotion=rejected；production_ready=false |

**本轮停止模型微调，不启动Experiment E。** 保留germany-reviewed-v1为development baseline。下一步仅提出two-stage architecture feasibility study：Stage1 building/road segmentation；Stage2 flooded/non-flooded classification。本轮没有实现或训练two-stage。

## 完成与验证

loss audit通过；训练前完整回归AI9、脚本33、训练40、Java核心53、HTTP1、SDK55及注册探针通过；另6项形态、3项排序测试通过，最终训练测试全集49项通过。训练40轮完成，原始best/last/history/report和learning curves齐全。
C、baseline候选及旧sampler所有封存文件SHA256再次核对保持一致；源代码和split哈希核对通过。未修改在线服务模型，production_ready=false。
报告与诊断脚本可复算；目录、完整配置、loss/source git/source SHA及差异见experiment_manifest.json；最终产物哈希和判定见completion_manifest.json。

![概率与PR](../experiments/diagnostics/experiment-d-probability-20260912/probability-comparison.png)
