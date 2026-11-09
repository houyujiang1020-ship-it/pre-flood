# E1 EMA 单变量实验

日期：2026-09-26。实验在 `germany-louisiana-domain-balanced-20260926` 基线上只增加 EMA；数据、split、缓存、采样、网络、损失、学习率、增强、30 epoch、选模指标和固定 0.5 阈值不变。预注册记录为 `experiments/germany-louisiana-domain-balanced-ema-20260926/preregistration.json`。

## 配置

- EMA 每个 optimizer step 更新，标准公式为 `ema = 0.999 × ema + 0.001 × online`。
- 训练反向传播继续使用 online 权重；验证和最佳 checkpoint 使用 EMA 权重。
- 断点同时保存 online、EMA 和 optimizer 状态，避免错误恢复。
- 预注册晋级条件：macro 必须高于 0.1438985793，且至少三类退化不超过 0.005。

## 结果

训练完成 30 epoch；最佳为 epoch 28。独立进程重载最佳 checkpoint 复算一致。

| 固定 0.5 Germany validation | 未淹建筑 | 受淹建筑 | 未淹道路 | 受淹道路 | macro |
| --- | ---: | ---: | ---: | ---: | ---: |
| 非 EMA 基线 | 0.20785 | 0.10421 | **0.20941** | 0.05412 | **0.143899** |
| EMA 0.999 | **0.21486** | 0.10365 | 0.19811 | **0.05879** | 0.143853 |
| EMA - 基线 | +0.00701 | -0.00057 | -0.01130 | +0.00467 | -0.000046 |

EMA 改善未淹建筑和受淹道路，但 macro 略低，且未淹道路退化超过 0.005。按预注册规则 `promotion=rejected`。不再用同一验证集搜索 EMA decay。

checkpoint：`models/experiments/germany-louisiana-domain-balanced-ema-20260926/best_model.pth`  
SHA-256：`7bd86f710de04935de200e61fcc567f911f7551cbc1aae2ee9c98b141ba2b11c`  
复算证据：`models/experiments/germany-louisiana-domain-balanced-ema-20260926/independent_reload_validation.json`

## 决定

- 保留非 EMA checkpoint 为当前开发验证 research leader。
- EMA 实现保留为配置化能力，但不用于下一轮基线。
- 下一步执行 E2：从 1300×1300 原始栅格生成高分辨率对齐缓存，训练 448×448 正类感知随机裁块，并用重叠滑窗在完整 validation 上评估。
- test 仍为空，`production_ready=false`。
