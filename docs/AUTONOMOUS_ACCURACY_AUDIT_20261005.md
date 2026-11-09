# 模型精度自主核查（2026-10-05）

## 结论

**本轮未证明精度提高，未替换线上模型。** 不能用已有训练标签的重复确认来制造“新标注”，也不能在已多次用于选模型的 Germany 18 张开发验证集上反复试到高分后宣称独立泛化。当前 E4 开发基线四类 macro IoU 为 0.160657，受淹道路 precision 为 0.113874；独立外部 IoU 仍未取得，`production_ready=false`。

## 已执行

1. 对 Louisiana-East 两张训练影像的 249 个建筑/道路对象逐对象查看灾前/灾后裁图。75 个高可信受淹，174 个证据不足而保持 `uncertain`；75 个均与已有训练标签 `yes` 相同。详见 `annotation_workspace/louisiana-east-review-v1/AGENT_REVIEW.md`。这批复核没有新增可用于独立测试的真值。
2. 对 E4 预先冻结一种不改权重的互斥输出规则：建筑、道路各自的受淹/未受淹通道取概率较高者，仅当概率超过 0.5 才输出；平局归未受淹。先保存输入 SHA、规则和晋级标准，再仅在现有 Germany 18 张开发验证瓦片评估一次。原 E4 重放与历史指标一致。
3. 互斥规则把受淹道路的预测像素从 38,481 降为 **0**，受淹道路 IoU 从 0.073678 降为 0，受淹建筑 IoU 从 0.116226 降为 0.001135，macro IoU 从 0.160657 降为 0.113292。两个状态的像素重叠虽然归零，但关键类别退化，故 `promotion=rejected`，没有接入推理服务。完整预注册与结果在 `experiments/e4-mutual-exclusion-20261005/`。
4. 核查本机 FloodNet 辅助数据：当前只下载了 Hugging Face `partial-train/0000.parquet`，100 行且仅有 `image.bytes/path`，**没有像素标签**。原发布方的完整 FloodNet 数据包含四类目标，但属于灾后无人机 RGB，无灾前卫星配对；不能把这份局部无标签文件充作本项目训练/外部测试真值。
5. 核查 SpaceNet 8 官方公开包：本机 Louisiana-West public test 无公开 GeoJSON 真值，已进行一次性无标签盲推理，精度字段必须保持空值。Germany 和 Louisiana-East 已用于训练/开发；不能重命名为新的独立测试集。

## 原因与有效后续

重叠输出并非简单的显示错误。开发集上受淹建筑预测的 39,138 像素中有 39,104 像素也被预测为未受淹建筑；受淹道路的 38,481 像素全部也被预测为未受淹道路。硬性互斥只掩盖这种概率排序偏差。此前因子化状态模型、建筑互斥损失、道路并集辅助损失及模型集成也已按各自冻结指标拒绝晋级，不应在同一验证折继续无边界调权重或阈值。

要可信地宣布“精度提高”，需要取得**尚未用于训练/调参、具有四类真值且语义兼容的外部区域**；在看到标签与推理结果前冻结来源、许可、配对、影像足迹、全部哈希、基线/候选、指标和晋级门槛。`scripts/freeze_external_test.py`、`scripts/evaluate_external_test_once.py` 已提供失败关闭的一次性流程。若之后使用 FloodNet 做辅助预训练，须先获得并核验完整标签，再作为单独跨传感器研究，不将 UAV 分数冒充卫星洪涝识别精度。

## 验证

`scripts/evaluate_e4_mutual_exclusion_20261005.py` 已编译并完成预注册、E4 checkpoint 重载、18 张开发瓦片测评与基线重放核对。`experiments/e4-mutual-exclusion-20261005/evaluation.json` 中 `baseline_replay_verified=true`、`promotion=rejected`、`independent_accuracy_verified=false`、`production_ready=false`。

原始来源：[SpaceNet 8 官方数据页](https://www.spacenet.ai/sn8-challenge/)；[FloodNet 官方仓库与标签定义](https://github.com/BinaLab/FloodNet-Supervised_v1.0)。
