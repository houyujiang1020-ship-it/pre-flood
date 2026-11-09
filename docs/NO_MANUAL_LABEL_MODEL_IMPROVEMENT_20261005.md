# 不新增人工标注的模型精度改进实验（2026-10-05）

## 结论

本轮完成三项预先固定规则的对照实验，**没有一项满足晋级条件，线上模型不变**。评价范围仅为现有 Germany 18 张开发验证瓦片，不构成独立测试集精度或正式比赛成绩。受淹道路的 E4 基线 precision 为 0.113874，说明误报仍是关键问题，不能仅凭某一项 IoU 上升宣称模型更准。

基线为 `models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth`，四类宏平均 IoU = 0.160657，固定阈值 0.5。三项实验没有新增人工标注，没有使用 Louisiana-West 无真值测试集选模型、调权重或调阈值。

| 固定实验 | 四类宏平均 IoU 变化 | 受淹道路 precision 变化 | 决策 |
|---|---:|---:|---|
| E4 与已有 domain-balanced 模型按 1:1 概率平均 | -0.006047 | -0.008658 | 拒绝 |
| E4 原图与水平翻转图各推理一次，概率平均 | +0.001130 | +0.002817 | 未达到预设 +0.005 宏 IoU 门槛，拒绝 |
| 在 E4 原训练损失上增加 0.25 × 道路并集 Dice 辅助损失，重训 30 epoch | +0.020001 | -0.007103 | 受淹道路 precision 下降；受淹建筑 IoU 下降 0.005914，超出预设 0.005 容差，拒绝 |

第三项说明道路定位可以通过现有道路标签改善：正常道路 IoU +0.061585、受淹道路 IoU +0.012328。但受淹道路召回从 0.172683 上升到 0.306628 的同时，precision 从 0.113874 降到 0.106772；这是更积极预测带来的权衡，不符合本轮以精确度为先的晋级条件。

## 实现与验证

- 推理实验及预注册、数值：`scripts/evaluate_e4_fixed_ensemble.py`、`scripts/evaluate_e4_flip_tta.py` 和 `experiments/e4-*-20261005/` 中的 `preregistration.json`、`evaluation.json`。
- 训练实验：`app/training/train_full.py` 可选 `road_union_aux_weight`，默认 0，保持既有配置行为；正类目标由现有正常/受淹道路标签求并集，不需要新标注。实验配置为 `config/training.e4-road-union-aux-20261005.json`；预注册、完整训练日志和评价在 `experiments/e4-road-union-aux-20261005/`。最佳权重仅为研究产物，位于 `models/experiments/e4-road-union-aux-20261005/best_model.pth`，`production_ready=false`。
- 训练相关 40 个单元测试通过。30 epoch 训练完成；最佳 epoch 21。独立进程重新加载最佳权重，在相同 18 张开发瓦片重放，各类 IoU 与训练记录差值均为 0，见 `checkpoint_replay.json`。这只验证可复现性，不是独立数据集验证。

核查命令（在项目根目录）：

```powershell
Get-Content experiments\e4-road-union-aux-20261005\checkpoint_replay.json
Get-Content experiments\e4-road-union-aux-20261005\evaluation.json
Get-Content experiments\e4-horizontal-flip-tta-20261005\evaluation.json
Get-Content experiments\e4-fixed-probability-ensemble-20261005\evaluation.json
```

重放脚本及实验结果文件采取一次写入防覆盖机制。重跑任一实验应使用新的实验 ID 和目录，不能覆盖本次证据。

## 方法依据和下一步

SpaceNet 8 的公开研究与方案使用了道路/建筑定位和洪水状态判断的分解方式；第五名方案也使用模型集成与水平翻转测试时增强。这些是候选思路，不保证迁移到本项目后提升。下一步应优先取得**独立、可核验且不新增人工标注**的真值来源（例如已有公开区域标签或正式提供的带真值案例），再对精确率、召回率和分区泛化做盲测。若没有独立真值，继续在同一 18 张开发瓦片上挑选方案会增加过拟合风险。

- [SpaceNet 8: The Detection of Flooded Roads and Buildings](https://openaccess.thecvf.com/content/CVPR2022W/EarthVision/papers/Hansch_SpaceNet_8_-_The_Detection_of_Flooded_Roads_and_Buildings_CVPRW_2022_paper.pdf)
- [SpaceNet 8 官方仓库](https://github.com/SpaceNetChallenge/SpaceNet8)
- [SpaceNet 8 第五名公开方案](https://github.com/motokimura/spacenet8_solution_5th-place)
