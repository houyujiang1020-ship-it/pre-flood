# 外部独立 test 冻结与一次性评估

带标签流程用于未来取得的、带四类真值且采用 SpaceNet8 目录和标签语义的数据。它不会把
Louisiana 开发折重新命名为独立测试，也不会因为推理成功而设置 `production_ready=true`。

## Louisiana-West public test 的无标签分支

本机已发现并解压官方 Louisiana-West public test：406 条 pre/post1 配对，没有公开 GeoJSON 真值。
它已通过独立的 `freeze_unlabeled_external_test.py` 冻结，并由
`run_unlabeled_blind_inference_once.py` 对 E4 按固定 0.5 完成一次性推理。该分支只输出概率分布、
预测覆盖率、状态重叠和固定抽样图，所有精度字段保持 null/false；不得运行带标签评估器，也不得
把这些输出用于训练、调阈值或选 checkpoint。结果见 `docs/LOUISIANA_WEST_BLIND_INFERENCE_20260926.md`。

## 输入条件

复制 `config/external-test-intake.example.json` 后填写原发布者、原始下载 URL、许可证名称与原文
URL、独立区域、灾害事件与日期、下载时间、数据根目录和 area 目录。还必须保存发布页/README 与
许可证原文的本地证据文件，冻结器会记录其 SHA-256。每个 area 必须包含：

- `<area>_label_image_mapping.csv`
- `PRE-event/`
- `POST-event/`
- `annotations/`

配对表必须提供 `label`、`pre-event image` 以及选定的 post-event 列。GeoJSON 必须真实覆盖未淹
建筑、受淹建筑、未淹道路和受淹道路；缺类不能按 IoU=1 处理。

## 第一步：冻结，禁止模型推理

```powershell
.\.venv-training\Scripts\python.exe scripts\freeze_external_test.py `
  --request config\external-test-intake.json `
  --reference-config config\training.germany-louisiana-domain-balanced-20260926.json `
  --output experiments\external-test-<event>\frozen-manifest.json
```

冻结器记录全部影像、标签、配对表和两个 checkpoint 的 SHA-256，检查四类 feature 支持，将每张
灾前影像 footprint 转换到 EPSG:4326，并与现有 Germany + Louisiana 全部 715 张开发样本比较。
存在相同影像或正面积空间相交即拒绝。冻结阶段不加载模型、不产生预测。

## 第二步：固定 0.5，一次性评估

```powershell
.\.venv-training\Scripts\python.exe scripts\evaluate_external_test_once.py `
  --manifest experiments\external-test-<event>\frozen-manifest.json `
  --output experiments\external-test-<event>\comparison.json
```

评估器先复核 manifest seal、全部文件哈希、参考配置和 checkpoint 身份。输出已存在时拒绝覆盖。
它在完全相同的冻结样本上比较 E4 与旧域平衡基线，阈值固定为 0.5，不训练、不校准、不选轮次。
研究晋级要求候选四类 IoU 和 F1 全部严格优于基线。

得到 comparison 后仍需运行 `scripts/verify_model_acceptance.py`。正式生产门禁还要求预先批准的
逐类阈值，以及绑定同一 checkpoint 的视觉质量、少数类 precision/recall 和稳定性签署证据。
在这些材料齐全前，独立 test 结果也保持 `production_ready=false`。
