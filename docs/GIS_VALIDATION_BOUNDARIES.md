# GIS 与生产模型验收边界（2026-08-30）

本记录是代码与已有证据的审查，不是新一轮 MapGIS 宿主终验。不能据此把剩余门禁改为通过。

## 数据语义

- SpaceNet8 建筑/道路及其 flooded 标记是受淹结构标签，不是连续、完整的洪水范围真值。受淹建筑面与道路缓冲区并集不能当作洪水范围或受淹面积。
- 掩膜像素、连通斑块和建筑实体数量不同；模型预测只提供候选核查区域。建筑相交不等于损毁，道路相交不等于不能通行。
- 当前没有已验收的社区边界、人口资料与真实/赛事认可资源台账。人口、社区风险和完整受淹面积必须显示未知/未验证，不能补零、从像素换算或虚构。
- 演练车辆及统一速度只用于闭环演示；不构成现实库存、实时路况或实际安全保证。

## 已有链路与真实差距

| 环节 | 当前实现/证据 | 仍需验收 |
|---|---|---|
| 实体暴露 | `ExposureAssessment` 按数据集、实体 ID、类型去重；保留斑块 ID | 真实实体源及原生查询结果的逐实体复核 |
| 原生相交 | `MapGisExposureQuery` 使用 `ModeIntersect`；检查打开状态和同 WKT，查询失败抛错 | 宿主内真实数据运行、跨 CRS 数据准备与失败场景验收；没有实现自动重投影 |
| 道路阻断 | `RoadClosurePlan`、道路/网络边映射以及已留存演练路由证据 | 权威通行状态、交通约束和闭路后的业务复核；候选道路不能自动判阻断 |
| 报告 | `HtmlOperationalReport` 已列出候选实体、核查证据、分配建议，并明确未知指标 | 完整洪水范围、面积、损毁核查、社区/人口指标与正式签署 |
| 地图与网络 | readiness 已有原生拓扑、演练阻抗、封路路线和地图显示证据 | 不重复实现已验收环节；4 项通过不等于完整原生业务终验 |

## 两层模型门禁

`config/model_acceptance.yaml` 区分 research_candidate 和 production_candidate。正式阈值和批准文件目前为空，生产层默认关闭。不得通过降低阈值或把训练结束视为验收来改变状态。

`scripts/verify_model_acceptance.py` 是等价离线证据验证器，不启动服务、训练、GUI，也不修改 checkpoint 或 production_ready。要求比较报告里的 checkpoint SHA256 与本地权重一致；每类有真值支持与 IoU/F1/precision/recall；研究层保守要求每类 IoU/F1 优于不同 baseline，并提供视觉、少数类、稳定性核查记录。当前报告缺少的指标不会被猜测填充。

本次实际读取 full-comparison-20260830.json 及其 SHA256 绑定的两份 calibration.json：完整 Louisiana 599 瓦片的四类 GT 均有支持，也包含 precision/recall；缺少受淹建筑支持仅是早期两瓦片报告的问题。tempered 校准模型在受淹建筑上的 IoU/F1 不优于第一轮，故研究筛选不通过；正式阈值、视觉/稳定性审核及未接触最终测试证据仍缺。`runtime/model-acceptance-diagnostic-20260830.json` 记录权重身份、类别支持与完整指标四项检查通过，其余不通过。重复研究基准不能伪装成盲测。

复现命令：

```powershell
.\.venv\Scripts\python.exe scripts/verify_model_acceptance.py --comparison models/checkpoints/full-comparison-20260830.json --candidate full-germany-tempered-20260830/calibration.json --baseline full-germany-20260830/calibration.json --checkpoint models/checkpoints/full-germany-tempered-20260830/best_model.pth --output runtime/model-acceptance-diagnostic-20260830.json
```

两种比较报告结构均可读取：旧版内嵌 evaluation；新版 report/report_sha256 引用。后者先校验原始报告 SHA256，再读取 test 指标，绝不从摘要猜测缺失指标。

核查 JSON 顶层使用 `checkpoint_sha256`，并分别提供 `visual_quality`、`minority_precision_recall`、`stability` 对象；每个对象含 `passed: true`、`reviewer`、`validated_at`、`evidence` 文件列表。文件相对核查 JSON 解析；其存在不替代人工核查内容真实性。

生产层额外要求独立区域评估、批准的全部四类指标阈值，以及 `approval_evidence` 指向的批准文件。批准文件必须含 `approved: true`、`approved_by`、`approved_at` 和与配置完全一致的 `thresholds`。阈值结构为四个指标名（class_iou/class_f1/class_precision/class_recall）到四类数值的映射。没有正式标准时保持 null。验证通过也只给出 production_candidate；production_ready 始终 false，部署晋级需另外完成正式验收。

readiness schema v2 保留 `key/passed/requirement` 与总数字段；`evidence` 改为所要求的列表，旧单路径可读 `evidence_path`。每项增加 name/status/validated_at/notes，证据文件不存在不能 pass。validated_at 是审计时间，不声称重跑了原生验收。真实台账和终验门禁继续关闭。
