# Experiment C 对照（2026-09-12）

## 决定

**Experiment C 不晋级；保留 germany-reviewed-v1 作为 development 基线，production_ready=false。** C完成40轮，最佳为第40轮；固定阈值、冻结开发阈值、新同集校准与两折OOF均未证明改善。没有运行Experiment D。

## 可比性

冻结split SHA256：`14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1`；train98/validation18/test0。审查197项已完成，未重做、未改split。没有读取Louisiana或future blind holdout。
C与旧sampler仅训练配置sampler不同；model_id/output_dir是保存身份变化。网络SiamUnet_diff、GroupNorm8、Adam、LR0.0003、seed20260912、512px、98步×40epoch、增强、0.5选checkpoint均相同。真实baseline已有Dice=0.5，用户明确确认继承；无新增Dice、class weight或Tversky。训练前experiment_manifest.json记录了完整配置和源码哈希。
旧sampler是epoch类别配额；C为6步周期2受淹道路+2受淹建筑+1foreground+1random，周期内打乱、按池打乱索引袋抽取。batch size仍为1，完整周期保证曝光；不声称每个batch能同时包含两个不同标签。最后2步不作完整周期保证。
本实验比较的是两种采样策略整体（比例、次序、池内覆盖），不能再把结果单独归因于其中某一个组成。单seed结果不证明所有class-aware策略无效。weighted仅是历史参考，不属于C的单变量对照。

## A：统一threshold=0.5

| 实验 | best epoch | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |
|---|---:|---:|---:|---:|---:|---:|
| weighted | 19 | 0.196683 | 0.001032 | 0.113490 | 0.000000 | 0.077801 |
| old_sampler | 37 | 0.226175 | 0.100068 | 0.001283 | 0.000000 | 0.081882 |
| class_aware | 40 | 0.216022 | 0.073605 | 0.000050 | 0.000000 | 0.072419 |

## B：原冻结开发阈值0.54/0.45/0.18/0.25

这些阈值来自旧sampler在Germany validation的校准；统一应用于三种权重，未修改候选阈值。weighted这里并非自身最优校准。所有分数都是开发验证结果。

| 实验 | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |
|---|---:|---:|---:|---:|---:|
| weighted | 0.197908 | 0.010192 | 0.125178 | 0.016502 | 0.087445 |
| old_sampler | 0.227066 | 0.101490 | 0.153674 | 0.053243 | 0.133868 |
| class_aware | 0.182863 | 0.074415 | 0.139946 | 0.030859 | 0.107021 |

## C：新development calibration（不替换冻结阈值）

仅在相同Germany validation按原0.01网格选择各类最大IoU阈值，得到 {'non_flooded_building': 0.39, 'flooded_building': 0.42, 'non_flooded_road': 0.12, 'flooded_road': 0.04}。

| 类别 | IoU | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| non_flooded_building | 0.230700 | 0.289218 | 0.532755 | 0.374908 |
| flooded_building | 0.075051 | 0.086970 | 0.353854 | 0.139624 |
| non_flooded_road | 0.145037 | 0.194216 | 0.364185 | 0.253332 |
| flooded_road | 0.038775 | 0.040556 | 0.468947 | 0.074656 |

新同集校准macro IoU=0.122391，不是独立精度。受淹道路阈值低至0.04，precision仅约4.06%，恢复召回同时带来大量误报。

## 同方法两折OOF阈值评价

沿用原assign_folds与阈值选择代码，每张验证图只使用另一折阈值；已核对C与旧模型两折样本列表完全一致。checkpoint仍由全部18张validation选择，故OOF只涉及阈值，并非完全独立的模型评价。

| 实验 | 普通建筑IoU | 受淹建筑IoU | 普通道路IoU | 受淹道路IoU | macro IoU |
|---|---:|---:|---:|---:|---:|
| old_sampler | 0.223417 | 0.054944 | 0.153166 | 0.024676 | 0.114051 |
| class_aware | 0.224587 | 0.029982 | 0.144371 | 0.016738 | 0.103920 |

## 实际曝光（每epoch均值）

旧sampler由原seed与源码重放，40轮的旧category_appearances逐一对上历史；以下普通类别按真实通道重新计数，避免与旧合并has_building/has_road混淆。多标签曝光允许重复计入多个类。

| 策略 | 普通建筑 | 受淹建筑 | 普通道路 | 受淹道路 | unique coverage |
|---|---:|---:|---:|---:|---:|
| old_sampler | 67.53 | 54.73 | 85.85 | 56.33 | 0.5355 |
| class_aware | 64.45 | 62.50 | 86.47 | 73.08 | 0.5143 |

## 晋级与 Experiment D

C在冻结阈值下三项重点类别全部下降，两折OOF也全部低于旧sampler；不满足保住受淹建筑和道路的要求，因此不晋级。development candidate继续指向旧sampler第37轮原始权重。
**值得进入D的方案设计，但本轮不运行D。** 概率正负部分重叠、校准后precision仍低，说明只改抽样与阈值没有解决道路空间识别。后续可预声明一个road-aware overlap loss单变量对照，从保留的旧sampler基线出发，先明确它与已有Dice=0.5的替代关系，避免把现有Dice重复叠加。
不能把本结果当作某种新损失必然有效的证据。验证集中仅2张受淹建筑、3张受淹道路；反复使用同一validation有开发过拟合风险，未来blind holdout继续封存，绝不参与调参。

## 验证与产物

完整run_tests.ps1退出0：AI9、脚本33、训练26（含新增8项sampler）、Java核心53、HTTP1、Java21 SDK55及注册探针通过。无新增GUI业务验收。
数值污染已修复为0.001282982062548399；来源为旧第37轮history及checkpoint相同指标。完整诊断见ROAD_PROBABILITY_DIAGNOSIS.md。
实验目录保留best_model.pth、last_model.pth、history.json、training_report.json、learning-curves.json、evaluation.json、development-calibration.json、threshold-oof.json、sample-exposure-comparison.json、experiment_manifest.json和completion_manifest.json。
概率诊断目录保留四类全部正/负概率NPZ、100-bin直方图JSON、PR曲线图、threshold表CSV、分位数及数值扫描证据。
模型未部署；candidate_type=development；production_ready=false；本轮blind_holdout_used=false；Louisiana/test均未使用。

## 复现入口

使用项目.venv-training Python执行app/training/diagnose_road_probability.py、train_full.py --config config/training.germany-reviewed-gn-class-aware-sampler-20260912.json和evaluate_experiment_c.py。已有训练目录拒绝覆盖；如需复现应另建输出目录，不能覆写冻结产物。render_road_probability.py使用Codex捆绑Python中的matplotlib生成图表；未改变训练依赖。
