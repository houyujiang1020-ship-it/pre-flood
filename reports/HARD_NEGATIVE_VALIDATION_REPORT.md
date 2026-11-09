# Hard-negative-top20 空间验证报告（2026-10-05）

> 结论：**KEEP_E4**。旧 Germany 18 张开发集上的 HN20-W3 小幅增益没有在新空间保留区复现。进一步筛出的 HN10-W5 虽在种子 42 提升，但三个种子中仅一个同时提升整体 IoU、受淹道路 IoU 和 precision；受淹道路 IoU 均值反而下降。这里的 E4 是同一新划分上重新训练的对照；正式 E4 权重没有在新保留区测试或被替换。新保留区仍是开发验证，`independent_external_test_verified=false`，`production_ready=false`。

## 1. Dataset Split

从旧 E4 的 697 张训练影像中划分：`TRAIN_NEW=579`（83.1%）、`SPATIAL_VAL_NEW=110`（15.8%）、隔离 8 张（1.1%）。整块 Germany 训练 AOI 与 Louisiana-East 最东侧 `x>=29` 作为空间保留区；Louisiana-East `x=28` 及跨缩放级别仍发生 bbox 重叠的 4 张瓦片进入隔离集。旧 Germany 18 张开发验证影像没有进入任何新训练或保留集。新保留区包含四类标签。清单及每个 PRE/POST/标签文件 SHA-256 位于 `experiments/hard-negative-validation-20261005/split/`。

## 2. Leakage Audit

冻结清单检查：样本 ID 重复 0、跨 split PRE/POST 路径重复 0、正面积 bbox 交叠 0、相邻同级瓦片跨 split 0。Louisiana-East AOI 名称同时出现在训练与保留区，但地理范围分离并有隔离带。首次按瓦片编号划分发现 4 张跨缩放级别重叠，失败证据保留于 `split-rejected-overlap/`，修正版通过 `tools/check_spatial_leakage.py`。旧 E4 和 E3c 检查点均见过保留区，故本实验**未用它们初始化或挖掘样本**。

## 3. Re-trained Baseline

从随机初始化在 `TRAIN_NEW` 内训练同架构对象 foundation，再以它初始化四类 E4。foundation 的内部选择集也只来自 `TRAIN_NEW`。5×80 短程 baseline 的四类预测均为 0，不具备参数筛选价值。15×200 完整预算的 E4 baseline 最佳 macro epoch=11，固定 0.5 macro IoU=**0.056340**；该 checkpoint 的受淹道路 IoU=**0.034970**、precision=**0.044650**、recall=**0.138906**。按受淹道路 IoU 选择的独立最佳 checkpoint 出现在 epoch 14，IoU=**0.037326**。两个最佳 checkpoint 均保存。

## 4. Fraction Search

固定权重 3，仅调整误报最多的训练瓦片比例。所有候选使用同一空间 split、基础初始化、种子 42、15×200 最大预算、Adam、学习率 0.0003、BCE+0.5 Dice、同步几何增强、固定 0.5 判定阈值。按**整体最佳 checkpoint** 比较：

| 比例 | macro IoU | 受淹道路 IoU | 受淹道路 precision | 结果 |
|---|---:|---:|---:|---|
| E4 新 baseline | 0.056340 | 0.034970 | 0.044650 | 参照 |
| HN10-W3 | 0.073269 | 0.032150 | 0.052520 | 整体升、受淹道路 IoU 降 |
| HN20-W3 | 0.059379 | 0.027960 | 0.041043 | 受淹道路 IoU/precision 降 |
| HN30-W3 | 0.064505 | 0.027799 | 0.057720 | 受淹道路 IoU 降 |
| HN40-W3 | 0.060528 | 0.024042 | 0.039480 | 受淹道路 IoU/precision 降 |

四组的整体最佳 checkpoint 都没有同时提升目标类别 IoU。若改为按受淹道路 IoU 选 checkpoint，HN10-W3 的 epoch 11 达到 IoU 0.042325、precision 0.057323、macro 0.059330，但普通道路 IoU 由 baseline 的 0.124406 降到 0.103592；不同轮次的指标不能合并。完整逐轮和两种 checkpoint 规则见 `experiments/hard-negative-validation-20261005/fraction-search/fraction_comparison.csv`。

## 5. Weight Search

按 fraction 阶段的道路最佳诊断，选择 10% 继续做 1.5／2／3／4／5 权重扫描。按**整体最佳 checkpoint**、固定 0.5：

| 权重 | 实际训练轮数 | macro IoU | 受淹道路 IoU | precision | recall |
|---:|---:|---:|---:|---:|---:|
| 新 E4 baseline | 15 | 0.056340 | 0.034970 | 0.044650 | 0.138906 |
| 1.5 | 15 | 0.066774 | 0.033989 | 0.041235 | 0.162076 |
| 2 | 14 | 0.064476 | 0.029999 | 0.046723 | 0.077326 |
| 3 | 15 | 0.073269 | 0.032150 | 0.052520 | 0.076549 |
| 4 | 11 | 0.059026 | 0.038068 | 0.046814 | 0.169263 |
| 5 | 15 | **0.077151** | **0.039156** | **0.054693** | 0.121142 |

权重 5 在种子 42 的同实际 15×200 步数下满足 macro、受淹道路 IoU 与 precision 同升且 recall 非零；普通建筑、受淹建筑与普通道路 IoU 也均高于 baseline。权重 2 和 4 提前早停，虽最大轮数与 patience 相同，实际步数不同，只作为探索性观察。权重 5 因此进入三种子验证。完整结果见 `experiments/hard-negative-validation-20261005/weight-search/weight_comparison.csv`。该选择仍发生在同一空间开发集上。

## 6. Multi-seed

最终候选为 HN10-W5。种子 42、3407、2026 分别成对训练；每对使用相同随机种子、基础权重、数据划分、优化器、增强、固定 0.5 阈值和 **15 epoch × 200 step** 实际预算。3407 的初次成对运行分别在 13/12 epoch 早停，因步数不等而被排除；重跑时将最少轮数设为 15，并从新 baseline 末轮重新挖掘训练集误报。下表全部采用各自的 `best_macro_iou.pth`，没有混合受淹道路最佳轮次。

| 种子 | 模型 | Building IoU | Flooded Building IoU | Road IoU | Flooded Road IoU | Macro IoU | Flooded Road Precision | Recall | F1 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | E4 新基线 | .043208 | .022774 | .124406 | .034970 | .056340 | .044650 | .138906 | .067578 |
| 42 | HN10-W5 | .094427 | .030128 | .144892 | .039156 | .077151 | .054693 | .121142 | .075362 |
| 3407 | E4 新基线 | .065539 | .025874 | .155143 | .039384 | .071485 | .048077 | .178853 | .075783 |
| 3407 | HN10-W5 | .059897 | .021054 | .098503 | .029465 | .052230 | .042498 | .087658 | .057244 |
| 2026 | E4 新基线 | .076610 | .022873 | .180510 | .038263 | .079564 | .046897 | .172067 | .073705 |
| 2026 | HN10-W5 | .107033 | .017901 | .148734 | .039479 | .078287 | .054492 | .125343 | .075960 |

以下为三种子的**均值 ± 样本标准差**，不是最优单次结果：

| 指标 | E4 新基线 | HN10-W5 | 均值变化 |
|---|---:|---:|---:|
| Building IoU | .061786 ± .017014 | .087119 ± .024403 | +.025333 |
| Flooded Building IoU | .023840 ± .001762 | .023028 ± .006348 | −.000813 |
| Road IoU | .153353 ± .028094 | .130710 ± .027958 | −.022643 |
| Flooded Road IoU | .037539 ± .002294 | .036034 ± .005691 | −.001505 |
| Macro IoU | .069130 ± .011790 | .069222 ± .014727 | +.000093 |
| Flooded Road Precision | .046541 ± .001741 | .050561 ± .006983 | +.004020 |
| Flooded Road Recall | .163275 ± .021375 | .111381 ± .020652 | −.051894 |
| Flooded Road F1 | .072355 ± .004266 | .069522 ± .010637 | −.002833 |

逐种子 macro / flooded-road IoU / precision 的配对变化分别为：42 `+.020811 / +.004186 / +.010043`，3407 `−.019256 / −.009919 / −.005579`，2026 `−.001277 / +.001217 / +.007595`。原始表在 `reports/multiseed_comparison.csv`；机器可读晋级判定在 `experiments/hard-negative-validation-20261005/multiseed/promotion_decision.json`。

## 7. Flooded Road Analysis

从新 baseline 的**末轮**权重仅在 `TRAIN_NEW` 579 张上挖掘，共找到 2,049,316 个按冻结标签定义的受淹道路 FP 像素。HN20-W3 选取排序最高的 116 张，权重 3；首轮 200 次采样中 76 次落在该集合，单瓦片最高占比 4%。最终 HN10-W5 及其三个种子的采样日志也未触发单瓦片占比 >10% 警告。使用加权有放回采样并保持每轮 200 步，没有整数复制数据；采样策略之外的训练配置经脚本核对。

三种子 HN 的受淹道路 precision 均值从 .046541 升至 .050561，但 recall 从 .163275 降至 .111381，IoU 从 .037539 降至 .036034。种子 3407 的 precision、recall、IoU 全部倒退；不能把种子 42 的增益推广为稳定效果。

原始对象属性审计显示 `flooded` 存在空值：训练集建筑 10,055 个、道路 2,109 个；保留区建筑 1,460 个、道路 415 个。原 E4 管线将空值映射为未受淹，但数据源没有足够语义证据确认空值是否代表“未知”。本次保留原映射以保证成对可比，同时将它标为潜在标签噪声；不能擅自将所有空值改成 255 或宣称这些预测均为真实误报。清单见 `experiments/hard-negative-validation-20261005/split/raw_status_audit.json`。

## 8. False Positive Spatial Analysis

对种子 42 的两个最佳 macro checkpoint，在 110 张空间保留影像上，以**标签道路**的 5、10、20 像素缓冲区分解 flooded-road FP：

| 缓冲 | E4 道路附近 / 远离 FP 像素 | 远离比例 | HN 道路附近 / 远离 FP 像素 | 远离比例 |
|---|---:|---:|---:|---:|
| 5 px | 124,821 / 215,492 | 63.32% | 122,353 / 117,393 | 48.97% |
| 10 px | 139,662 / 200,651 | 58.96% | 132,572 / 107,174 | 44.70% |
| 20 px | 166,080 / 174,233 | 51.20% | 150,240 / 89,506 | 37.33% |

HN 在种子 42 显著减少远离道路的误报，但跨种子指标表明这一局部效果不足以支持晋级。逐瓦片、逐缓冲结果为 `reports/flooded_road_fp_spatial_analysis.csv`。由于 HN 的 5px 远离比例仍有 48.97%，额外试验了**非硬门控** soft road prior：`P_final=P_model×(alpha+(1−alpha)×P_road_prior)`，道路先验来自本次干净训练的 foundation。固定阈值 .5 下，alpha 1.0 的 IoU/precision/recall 为 `.039156/.054693/.121142`，alpha .5 为 `.042881/.067941/.104147`；alpha .7/.8/.9 的 IoU 依次为 `.040588/.039912/.039448`。alpha 始终大于零，且只在同一开发集上诊断，**未加入正式推理**。详见 `experiments/hard-negative-validation-20261005/failure-analysis/soft_road_prior_diagnostic.csv`。

## 9. Threshold Diagnostic

所有主比较一律使用固定阈值 **0.5**。HN10-W5 种子 42 在该阈值的 flooded-road IoU/precision/recall/F1 为 `.039156/.054693/.121142/.075362`，预测像素 253,617。模型确定后才在同一空间开发集单独扫阈值；其中阈值 **0.30** 的 IoU/precision/recall/F1 为 `.040455/.050507/.168923/.077763`，预测像素 382,957。这只是开发集最优诊断，不可拿来和 baseline 的固定 .5 做模型晋级比较，也没有外部测试支持部署。完整网格见 `experiments/hard-negative-validation-20261005/threshold-search/hn10-w5-seed42/threshold_search.csv`。

## 10. Failure Cases

训练集 PRE/POST/GT/PRED/FP/FN 图、每瓦片 FP 数量与比例位于 `experiments/hard-negative-validation-20261005/failure-analysis/train-mining-seed42/`；空间保留区 110 张的对应诊断分别位于 `failure-analysis/validation-baseline/` 和 `failure-analysis/validation-hn10-w5/`，并保存误报最高三张的图。种子 42 的保留区 flooded-road FP 总像素从 340,313 降至 239,746，但 FN 与 precision/recall 的取舍必须结合上表审阅。图像用于定位错误，不能当作人工核验的真值。

## 11. Stability

旧 18 张 Germany 开发集上的 HN20-W3 提升未在本次新空间同预算验证中复现。探索后 HN10-W5 的三种子结果只在 42 上同时提升三个关键指标，3407 全面回退，2026 的 macro 小幅下降；普通道路 IoU 在 3407 和 2026 分别下降 `.056640`、`.031776`，超过预设的主要类别灾难性回退阈值 `.02`。HN 受淹道路 recall 三个种子均下降，且标准差扩大。因而当前证据是**不稳定**，而不是“稳定提高 flooded-road 精度”。空间保留区以 Germany 域为主；Louisiana-East 最东部影像在早期项目研究中可能被观察过。它是新训练的空间开发验证，仍不是全新独立外部带标注测试。

## 12. Promotion Decision

**KEEP_E4**：保留既有 E4 服务权重，不发布 HN10-W5，不改服务阈值或道路后处理。晋级规则要求跨种子平均 macro、flooded-road IoU 和 precision 同升、recall 非零、至少两个种子联合改善，且主要类别不发生灾难性回退；本次仅满足部分均值条件，联合改善 1/3，存在两次普通道路回退。`production_ready=false`。下一步需要来源明确的外部带标注 PRE/POST 数据，尤其核清 `flooded=null` 语义，并做一次预先冻结规则的独立测试。

本阶段 P2 的动态 hard-negative mining 尚未实现；现有 HN 排名在每次成对试验前由对应新 baseline 的训练集末轮检查点静态计算。该未完成项不会改变上述不晋级决定。E3c 分支已是拒绝实验（旧记录 macro IoU .049110、受淹道路 IoU 0），本阶段没有继续训练；合成 pseudo-label 仅保留代码，没有用于训练。
