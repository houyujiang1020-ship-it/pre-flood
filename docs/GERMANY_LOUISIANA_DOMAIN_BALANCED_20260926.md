# Germany + Louisiana-East 域平衡训练结果

日期：2026-09-26。该实验只改变训练采样策略，用于检验 Louisiana-East 样本量远大于 Germany 时的域偏置。模型仍为研究候选，未修改线上服务或 `production_ready=false`。

## 实验边界

- 数据和 split 与 2026-09-16 训练一致：Germany train 98、Louisiana-East train 599、Germany validation 18、test 0。
- 模型、512×512 预处理、GroupNorm8、BCE + 0.5 Dice、学习率、30 epoch、空间增强和固定 0.5 阈值均保持不变。
- 唯一实验变量为 sampler：每轮 400 次出现，Germany/Louisiana 各 200 次；再在每个域内满足受淹建筑 25%、受淹道路 25%、建筑 50%、道路 50% 的最低出现比例。采样有放回，不同时启用正类像素权重。
- 配置：`config/training.germany-louisiana-domain-balanced-20260926.json`；实现：`app/training/domain_balanced_sampler.py`。

## 结果

30 epoch 正常完成，最佳为 epoch 30。独立 Python 进程重载最佳 checkpoint，在相同 18 张 Germany validation 上复算得到完全相同的固定 0.5 指标。

| 同一 Germany validation、固定 0.5 | 未淹建筑 | 受淹建筑 | 未淹道路 | 受淹道路 | macro |
| --- | ---: | ---: | ---: | ---: | ---: |
| Germany-only | 0.22618 | 0.10007 | 0.00128 | 0.00000 | 0.08188 |
| Germany + Louisiana 普通正类采样 | 0.12824 | 0.05272 | 0.22751 | 0.08152 | 0.12250 |
| Germany + Louisiana 域平衡采样 | **0.20785** | **0.10421** | 0.20941 | 0.05412 | **0.14390** |

与普通合并训练相比，macro 绝对增加 0.02140（相对约 17.5%），两类建筑恢复明显，但两类道路回落。与 Germany-only 相比，macro 绝对增加 0.06202；除未淹建筑略低外，其余三类更高。该结果说明域平衡有效缓解了 Louisiana 数量优势造成的建筑退化，但没有解决道路与建筑之间的性能竞争。

最佳 checkpoint：`models/experiments/germany-louisiana-domain-balanced-20260926/best_model.pth`  
SHA-256：`d464f11a6bbd5293229fd60d76ca0d8717929ad4445e1ccf79cd5d04bd8ab38b`  
独立重载证据：`models/experiments/germany-louisiana-domain-balanced-20260926/independent_reload_validation.json`

## 决定

- 该模型是当前固定 0.5、相同 Germany 开发验证口径下的研究领先者，但不是独立测试精度。
- `promotion=pending_independent_test`：保留 checkpoint，不替换线上模型，不调整开发阈值。
- 当前 18 张验证片已被多轮研究反复使用；后续算法选择应改用空间分组交叉验证，未来 test 到位后只做冻结评估。
- 下一项低成本单变量实验为 EMA；随后验证原分辨率裁块/重叠推理，再进入 foundation 辅助监督与 soft-gated 双时相结构。完整依据见 `docs/OPEN_SOURCE_ALGORITHM_ADAPTATION_20260926.md`。

验证：domain sampler 与训练相关单元测试 18 项通过；独立进程重载 checkpoint 后，四类 IoU、macro 和 checkpoint 选择分数完全一致。
