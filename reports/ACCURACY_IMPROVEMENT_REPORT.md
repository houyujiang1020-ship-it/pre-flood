# MapGIS-FloodGuard AI 精度改进实验报告（2026-10-05）

## 1. Baseline

研究基线 E4 为双时相 RGB、GroupNorm SiamUnet_diff、四个独立 sigmoid 输出，检查点 `models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth`，SHA-256 `ba2da68622d79683de2b6a9c30209c509d21cc44c1693e9118a061616c93e4bc`。固定 0.5 阈值、18 张德国开发验证影像上的 macro IoU 为 **0.160657**；四类 IoU 分别为 0.225711、0.116226、0.227015、0.073678。受淹道路 precision 为 0.113874，recall 为 0.172683。原始 E4 未删除或替换。

## 2. Changes

- 新增独立的类别感知同步裁剪，支持受淹道路、受淹建筑、正常对象、背景的可配置抽样；原训练器仅通过可选配置启用。
- 新增全训练集 flooded-road 假阳性挖掘，保留地图对照图、误报 CSV 和训练集证明；可以只对误报最多的前 20% 训练瓦片施加 2–5 倍权重。
- 新增 E3c 单时相 foundation + 双时相受淹对象状态分支的软概率融合研究实现，以及 focal BCE + Dice 训练器。这里的状态不是连续真实洪水面。
- 新增 GIS 建筑/道路弱标签栅格化；道路缓冲使用本地 UTM 米单位，nodata 保留为 ignore，不将空间对象标签冒充洪水真值。
- 新增双教师、多视角、高置信伪标签过滤、255 ignore 和 Mean Teacher 学生训练器。合成烟测样本被明确标记为不可用于正式训练。
- 新增固定阈值评估、每类阈值开发诊断、模型晋级门槛、可重复入口和单元测试。FastAPI、Java、MapGIS 和四类输出合同未修改。
- 新增独立 `extended_prediction.json`/概率图导出工具，保持原 `flood_prediction.json` 不变；当前仅在合成影像上做执行烟测。

## 3. Dataset

冻结清单：训练 697 张（Germany 98 / Louisiana-East 599），德国开发验证 18 张，带标注独立测试 0 张。没有重复样本 ID、跨 split 重用 PRE 路径或同 AOI 正面积 bbox 重叠。德国 18 张已经反复用于研究判断，因此是开发集，不是新的盲测集。Louisiana-West 公开测试没有四类真值，已冻结，不参与训练或调参。审计证据在 `experiments/accuracy-pipeline-20261005/split_audit.json`。

## 4. Pseudo Labels

采用 E4 与类别裁剪候选两个冻结教师，并对原图、水平翻转、垂直翻转做一致性过滤，逐类低/高阈值及方差阈值，未达一致或 nodata 像素写 255。仅有一张**合成**地理影像做 512×512 技术烟测，没有正伪标签；它不能证明模型可以从外部无标注影像改善精度，也不得被当作真实训练数据。外部可训练的新增 PRE/POST 成对影像及独立空间验证尚未到位。统计：`experiments/accuracy-pipeline-20261005/pseudo-smoke-512/pseudo_label_stats.json`。

## 5. Training

GPU：NVIDIA GeForce RTX 4050 Laptop GPU；Python 3.10.11，PyTorch 2.5.1+cu121。类别裁剪、foundation/status 融合、以及 hard-negative-top20 各做隔离的短程实验，使用原 E4 split 和固定 0.5 开发评估。hard-negative-top20 从 697 张训练瓦片中选误报最高的 140 张，权重 3，2 epoch × 80 steps/epoch。训练集预测共检出 2,210,463 个 flooded-road FP 像素；这不是验证精度。Teacher–Student 用合成数据跑通 1 step，仅验证执行与检查点保存。

## 6. Metrics / Baseline Comparison

| 模型 | 建筑 IoU | 受淹建筑 IoU | 道路 IoU | 受淹道路 IoU | macro IoU | 受淹道路 precision | 判定 |
|---|---:|---:|---:|---:|---:|---:|---|
| E4 | 0.225711 | 0.116226 | 0.227015 | 0.073678 | 0.160657 | 0.113874 | 保留基线 |
| 类别裁剪短程实验 | 0.217997 | 0.126801 | 0.223714 | 0.083367 | 0.162969 | 0.134080 | 拒绝；macro 未过 +0.005 且建筑退化 |
| E3c + 受淹状态软融合短程实验 | 0.016478 | 0.003129 | 0.176832 | 0 | 0.049110 | 0 | 拒绝 |
| 训练集误报前 20% 重采样短程实验 | 0.225743 | 0.125883 | 0.232467 | 0.079583 | **0.165919** | **0.128625** | 仅开发候选 |

完整机器可读数据：`reports/model_comparison.csv`、`experiments/accuracy-pipeline-20261005/hard-negative-top20-metrics.json`。不同小数末位来自独立重载与浮点累计，结论不受影响。

## 7. Flooded Road

与 E4 相比，前 20% 误报重采样候选的受淹道路 IoU +0.005905，precision +0.014751；recall 约 0.172683，非零预测像素 34,068。所有候选仍使用固定 0.5 阈值。阈值网格仅作为旧开发集诊断，不把 0.3 等开发最优值推向生产。硬互斥方案此前使受淹道路预测降为 0，故未采用。

## 8. Comparison and Ablation

短程实验呈现三点：仅强化稀有类裁剪不足以稳定通过整体门槛；在缺少连续洪水真值的情况下，foundation + 状态分支的道路类塌缩；训练集内的高误报定向重采样在同一开发集上达到了预先设定的候选门槛。这些是开发观察，不能推广为新地区精度。全量误报 CSV、前三位 PRE/POST/GT/PRED/FP/FN 图在 `experiments/accuracy-pipeline-20261005/train-failure-full/`。

## 9. Limitations

- 没有独立四类带标注测试集；无法计算最终泛化精度或比赛成绩。
- Germany 验证集反复使用，存在研究选择偏差；+0.005262 macro 增益不能视为独立证据。
- 真实外部成对无标注影像尚未进入伪标签训练；合成烟测没有正样本。
- 当前洪水语义为对象受淹状态，不存在由该模型核验的连续真实洪水面；GIS 风险分析必须继续依赖真实洪水面输入。
- 短程候选仅 2 epoch × 80 steps，不是经独立盲测完成的最终模型；未做大规模多种子或跨区域统计检验。
- 训练标签中的未知受淹状态可能被映射为未受淹；训练集内挖掘的“假阳性”按现有标签定义，不等于所有像素都经人工核实为误报。
- 未触碰 MapGIS 真机授权、真实 GUI 截图与 Java 侧业务验收。

## 10. Promotion Decision

预设门槛：macro IoU 增幅至少 0.005、任一类回退不超过 0.005、受淹道路 IoU 上升、precision 不下降且召回与预测像素非零。hard-negative-top20 **通过开发候选门槛**（macro +0.005262），文件 `experiments/accuracy-pipeline-20261005/hard-negative-top20-promotion.json` 明确标记 `independent_test_accuracy_verified=false` 与 `production_ready=false`。正式服务继续使用原配置/模型。下一次有效晋级需要冻结新的空间独立四类测试或可审计外部标签，再做一次盲评。

## 11. Verification

- Python 训练与采样相关回归：110 passed。
- FastAPI 兼容性定向测试：3 passed（服务环境 `.venv`）。
- 一键审计入口已执行，E4 重载得到 macro IoU 0.160657。
- 真实 MapGIS 宿主与独立比赛精度：本阶段未验证。

## 12. Reproduction

在仓库根目录运行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_accuracy_pipeline.ps1 -Mode Audit -RunId <new-id>` 可重新审计/复评 E4。训练需把新实验配置的 `model_id` 和 `output_dir` 指向空目录，再运行 `-Mode Train -Config <new-config> -RunId <new-id>`。`-MineFullTrain` 可额外挖掘全训练集 FP。详细入口、配置和证据解释见 `docs/MODEL_ACCURACY_PIPELINE.md`。
