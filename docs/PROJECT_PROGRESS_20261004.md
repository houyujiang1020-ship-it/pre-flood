# MapGIS-FloodGuard 项目进度与第三阶段验收状态

更新日期：2026-10-04。实际代码仓库：`C:\Users\33076\Desktop\高级开发`。

## 当前进度

| 模块 | 当前状态 | 可核验依据 |
|---|---|---|
| AI 遥感洪水检测与 FastAPI + Java 调用 | 已有实现；模型精度与现场泛化不在本次验证范围 | 现有训练、服务、桌面代码与既有项目报告 |
| FloodGuardMainWindow 与 MapGIS MapControl | 代码已接入，宿主 GUI 尚未运行验收 | `FloodGuardMainWindow.java`；插件注册探针通过 |
| 灾损对象专题与点击查询 | 代码已接入，宿主 GUI 尚未运行验收 | `MapGisDamageThematicImporter.java`、`DamageThematicPanel.java` |
| 路网拓扑、阻抗、绕行与人口格网 | 已有实现；需按各自验收记录区分实测与待测 | 现有路网、调度、人口分析代码和数据 |
| 洪涝风险评估与风险分区 | SDK 代码完成并通过编译；原生运行待验收 | `FloodRiskAssessment.java`、`MapGisRiskThematicWriter.java`、`RiskAssessmentPanel.java` |
| 应急路径规划与资源调度 | SDK 代码与 GUI 入口完成并通过编译；原生路径和截图待验收 | [第四阶段说明](EMERGENCY_DISPATCH_20261004.md) |

## 第三阶段已实现的代码路径

“风险评估”菜单进入原生 MapGIS 图层选择页。行政区、人口格网、真实洪水面、正常/受淹建筑、正常/受影响/阻断道路均从已加载的 MapGIS `VectorLayer` 选择；行政区名称字段及 `resource_distance_risk` 字段可配置。若必需图层已加载，打开页面自动执行；也可手动刷新与重算。

空间计算由 MapGIS SDK 的 `GeometryOperator.project`、`overlay`、`calculateArea` 和 `calculateLineLength` 完成。建筑风险为受淹建筑数 / 区域建筑总数，人口风险按真实洪水面与 100 m 人口格网的相交面积分摊，交通风险为阻断道路长度 / 区域道路总长度。综合分数为 `0.4 × 建筑风险 + 0.3 × 人口风险 + 0.2 × 道路风险 + 0.1 × 应急资源距离风险`；风险等级采用 `[0,0.3)` 低、`[0.3,0.6)` 中、`[0.6,1]` 高。

缺少真实洪水面、人口格网或有效人口时，受影响人口、人口风险和综合分数保持空值，报告状态为 `PARTIAL`；建筑和道路指标仍可输出。缺少有效的 `resource_distance_risk` 或分母为零也不会被默认为零。完整分数的行政区写入 MapGIS HDF 原生面要素类，按低/中/高风险使用绿/黄/红填充；地图点击通过 MapGIS `identifySelections` 查询属性。导出路径为每次运行的 `risk-<UUID>/risk_report.json`、`risk_report.html`、`risk-thematic-manifest.json`，点击后保存 `selected-risk-area-<UUID>.json`。工作台截图及日志由“保存验收截图”按钮或分析后自动保存。

## 本次验证结果

- `scripts/build_mapgis_plugin.ps1`：**通过**；62 项 JUnit 测试，失败 0，错误 0；插件注册探针通过。原始日志见 [risk-assessment-build-20261004.log](risk-assessment-build-20261004.log)。这证明 SDK 符号、Java 编译和非 GUI 测试通过，不等同原生空间结果正确性验收。
- `scripts/verify_mapgis_host.ps1`：**未通过启动前检查**。当前 Windows 会话不是 MapGIS 官方桌面宿主要求的管理员会话，脚本在启动宿主前停止；未进行授权或 GIS 运行测试。原始日志见 [risk-assessment-host-20261004.log](risk-assessment-host-20261004.log)。
- 本次**未生成真实 `risk_report.json`、HTML 实例、风险评估页面截图、风险专题地图截图或点击查询截图**。目前仓库缺少可用的真实洪水面 MapGIS 图层和已核验的行政区 `resource_distance_risk` 字段，且当前会话无法启动官方宿主；不能把示例数据或合成截图当作比赛验收材料。

## 后续验收所需输入与步骤

1. 在可运行 MapGIS 官方桌面宿主的 Windows 会话中，加载具有米制投影的行政区、真实洪水面、人口 100 m 格网及四类建筑/道路专题数据；行政区需有唯一名称及 `[0,1]` 的 `resource_distance_risk` 数值字段。正常、受影响与阻断道路图层应为互斥分类，避免道路总长重复计数。
2. 运行 `scripts/build_mapgis_plugin.ps1` 与 `scripts/verify_mapgis_host.ps1`，打开 FloodGuard 风险评估页并核查投影、叠加、人口分摊和分区属性。
3. 保存风险评估页、专题地图和点击属性三类**真实运行截图**，保留对应 `risk_report.json`、HTML、专题清单、选择对象 JSON 及运行日志；以源数据独立复核至少一个区域的建筑数、人口和道路长度。

当前结论：第三阶段**实现到可编译、可部署的 SDK 代码与 GUI 入口**，尚未达到用户要求的原生运行与比赛截图验收完成状态。
