# 道路概率诊断（2026-09-12）

仅使用冻结 Germany validation 18 张的有效监督像素。当前 sampler checkpoint 第37轮。没有使用 Louisiana、test 或 future blind holdout。本轮不重复人工审查，不改变 split。

## 概率分布

正负分布均按各自像素总数归一化；直方图使用对数纵轴，避免大量背景掩盖正类。PR 曲线采用 0.01 阈值网格，CSV保留 TP、FP、precision、recall、IoU；NPZ保存全部有效正负像素概率。

| 类别 | GT组 | p05 | p25 | p50 | p75 | p95 |
|---|---|---:|---:|---:|---:|---:|
| non_flooded_building | positive | 0.003387 | 0.132968 | 0.506835 | 0.661197 | 0.744708 |
| non_flooded_building | negative | 0.000000 | 0.000005 | 0.000069 | 0.000525 | 0.031526 |
| flooded_building | positive | 0.013727 | 0.136125 | 0.394068 | 0.573369 | 0.672021 |
| flooded_building | negative | 0.000000 | 0.000025 | 0.000233 | 0.001350 | 0.051766 |
| non_flooded_road | positive | 0.005745 | 0.025854 | 0.112185 | 0.286021 | 0.417486 |
| non_flooded_road | negative | 0.000064 | 0.002370 | 0.007644 | 0.019825 | 0.123010 |
| flooded_road | positive | 0.001135 | 0.021312 | 0.080095 | 0.201573 | 0.349206 |
| flooded_road | negative | 0.000006 | 0.000632 | 0.002902 | 0.009763 | 0.088080 |

## 阈值与响应

| 类别 | 阈值 | Precision | Recall | IoU |
|---|---:|---:|---:|---:|
| non_flooded_building | 0.50 | 0.290171 | 0.506303 | 0.226175 |
| non_flooded_building | 0.54 | 0.307571 | 0.464529 | 0.227066 |
| flooded_building | 0.50 | 0.120466 | 0.371450 | 0.100068 |
| flooded_building | 0.45 | 0.116690 | 0.437931 | 0.101490 |
| non_flooded_road | 0.50 | 0.175510 | 0.001291 | 0.001283 |
| non_flooded_road | 0.18 | 0.199327 | 0.401537 | 0.153674 |
| flooded_road | 0.50 | 0.000000 | 0.000000 | 0.000000 |
| flooded_road | 0.25 | 0.070578 | 0.178160 | 0.053243 |

## 解释

1. 普通道路正类概率整体偏低，但相对负类有区分信号：正类中位数0.1122，负类0.0076。然而负类p95=0.1230已超过正类中位数，重叠不可忽视。
2. 受淹道路不能归因为“只是 calibration 偏低”：正类中位数0.0801，负类p95=0.0881；正类p25=0.0213，负类长尾也覆盖该范围。阈值无法消除排序/空间识别错误。
3. 两类道路不是完全不可分，也不是充分分离；大量负像素即使只有较小比例进入高概率尾部，也会形成大量FP。PR与IoU比单独ROC更能揭示当前少数类问题。
4. 0.5高于两类道路正类p95，绝大多数真正道路被判负，受淹道路在该阈值TP为0。
5. 0.18/0.25把部分正类中高概率尾部纳入预测，恢复召回，同时也增加FP；恢复响应不等于可靠分类。旧同集校准IoU仅0.15367/0.05324，折外阈值IoU0.15317/0.02468，仍明显不足。

## 旧 sampler 审计

旧实现是 overlapping category quotas，不是任意正类共享一个池。受淹建筑和受淹道路至少各ceil(98×0.4)=40次，建筑/道路（含受淹）至少各59次，背景最多9次；满足配额后随机补足，再对整个epoch打乱。有放回，重叠样本对多个配额计数。
真实训练类别：普通建筑61、受淹建筑21、普通道路92、受淹道路28、纯背景0。一个样本可多标签。旧has_building=68/has_road=95是包含受淹类别的合并语义。
新 sampler 保持batch size1，每6个连续步骤由受淹道路2、受淹建筑2、foreground1、random1组成，周期内打乱，每池用打乱的索引袋循环取样；缺失类别显式回退random并记录。因为batch size1，不能保证每个batch同时含两个不相交类别；完整6步周期保证两类曝光。最后不足6步的尾部不作此保证。

## 数值修复与边界

原污染单元格已从 history.json 第37轮与 best_model.pth 的 history 一致恢复为 **0.001282982062548399**；独立道路诊断使用计数除法给出0.0012829820879787562，末位差来自浮点精度。修复来源及Markdown/JSON扫描清单见numeric-repair-audit.json。
此前“以概率校准问题为主”的表述过强，修订为概率整体偏低并伴随正负重叠。OOF只把阈值选择折外化，checkpoint仍由全部validation选择，不能称独立模型精度。
candidate_type=development；production_ready=false；冻结开发阈值0.54/0.45/0.18/0.25仅属于Germany development validation。

![概率分布与PR曲线](../experiments/diagnostics/road-probability-20260912/probability-histograms-pr.png)
