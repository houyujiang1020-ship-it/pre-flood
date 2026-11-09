# Gate 5 MapGIS GUI Evidence Checklist

本清单必须由真实授权 MapGIS Desktop 操作产生。每张截图都要保留原始 PNG，并在 `gui-evidence-manifest.json` 登记时间、步骤、说明和 SHA-256。禁止使用合成图或其他 GIS 软件截图。

1. `screenshot-01-plugin.png`：MapGIS Desktop 中 FloodGuard 插件和版本可见。
2. `screenshot-02-gt-mode.png`：模式选择为 `GT VALIDATION · 官方真值`，且 AI 推理按钮禁用。
3. `screenshot-03-buildings.png`：Affected Buildings 图层可见，选中建筑显示实体 ID 与 flooded 属性。
4. `screenshot-04-roads.png`：Affected Roads 图层可见，选中道路显示实体 ID；界面不声称 road closure。
5. `screenshot-05-community.png`：BKG Dernau Gemeinde 边界与来源字段可见。
6. `screenshot-06-risk.png`：人口结果与 Risk Zone 专题可见；若风险仍因输入缺失阻断，截图需显示 BLOCKED，不能伪造 PASS。
7. `screenshot-07-report.png`：从本次 run 生成的 HTML 报告和相同 run_id 可见。

运行目录还必须包含真实 `desktop.log`、环境版本、插件哈希、数据集哈希、社区/人口/风险输出及实体抽样证据。自动化环境不可用时由用户按本清单操作，随后只运行哈希登记工具，不修改 validator 判据。
