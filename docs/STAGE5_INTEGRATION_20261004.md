# 第五阶段：系统集成与比赛展示验收记录

更新：2026-10-04。该记录区分可编译代码、实际 MapGIS 运行及比赛验收；不能将演练假设或单元测试当作宿主运行截图。

## 本轮实现

| 要求 | 代码状态 | 可核查文件 |
|---|---|---|
| 案例创建、加载、删除 | 已实现，受控目录内操作；删除不触碰源文件 | `ScenarioManager.java`、`ScenarioPanel.java` |
| 一键步骤与失败停机 | 八步串行、逐步检查持久化证据、失败日志 | `DemoController.java`、`FloodGuardMainWindow.java` |
| 工具栏、状态栏、态势面板 | 已接入；指标仅在原生分析回调后更新 | `FloodGuardMainWindow.java`、`DashboardPanel.java` |
| 原生灾损、风险、路网、资源复用 | 已在案例演练入口编排；按精确 MapGIS URL 绑定风险图层 | `MapGisDamageThematicImporter.java`、`RiskAssessmentPanel.java`、`EmergencyDispatchPanel.java` |
| 综合 HTML 报告 | 按七部分输出；缺风险、路线或资源证据时拒绝生成 | `ReportGenerator.java` |
| 七张阶段截图 | JavaFX 工作台真实渲染后保存；尺寸或地图图层不满足则拒绝 | `ScreenshotManager.java` |
| 无外部数据演示包 | 现有原始素材可离线核查；完整原生数据包未完成 | `DemoDataset.java`、`data/acceptance/gate5-v1`、`data/demo/dispatch-spacenet8-endpoint-v2` |

## 演练输入与执行条件

案例字段包括灾前/灾后影像、对象预测 JSON、行政区、人口格网、真实洪水面、原生路网、原始道路的 MapGIS URL，资源库清单和道路状态核查单，以及车辆、目标和风险字段。所有空间分析仍使用 MapGIS SDK。演练回放只能说明给定对象预测进入 GIS 后的业务路径；当前 FastAPI 输出洪水掩膜，并不直接生成与建筑/道路对应的 `flood_prediction.json`。因此 `LIVE_AI` 完整演练会在缺失对象桥接处中止，`REPLAY` 在 AI 证据和报告中均会标明结果回放。

人口暴露风险只在明确洪水面图层存在时计算；资源距离风险只从行政区字段读取。封路核查单必须与当前路网 URL、边数和源道路映射一致；资源必须在 MapGIS 原生空间库中。上述缺失或不一致时，一键流程保存失败步骤及原因，不填零、不构造成功报告。

`outputs/screenshots/demo-*/` 预期保存 `01_系统主页.png` 至 `07_综合报告.png`；`outputs/demo-runs/demo-*/demo-progress.json` 保存阶段证据路径；报告预期写入 `outputs/final-reports/report-*/FloodGuard_Final_Report.html`。当前尚未有成功演练实例，因此这些文件不能作为本次已产出的验收样本。

## 本轮验证

- `scripts/build_mapgis_plugin.ps1`：通过；67 项 JUnit 测试全部通过，插件注册探针通过。原始日志：[stage5-build-20261004.log](stage5-build-20261004.log)。这覆盖 Java/SDK 编译和非 GUI 逻辑，不证明地图渲染、空间运算数值或路线运行正确。
- `scripts/verify_mapgis_host.ps1`：未通过前置条件。当前会话非管理员会话，官方宿主在启动前被脚本阻止；未检查授权，也未运行演练 GUI。原始日志：[stage5-host-20261004.log](stage5-host-20261004.log)。
- 尚无真实的七张阶段截图、点击区域属性截图、完整 `demo-progress.json` 或 `FloodGuard_Final_Report.html` 实例。

## 达到最终验收仍需完成

1. 用 MapGIS SDK 将内置原始素材整理成同一米制投影的行政区、人口格网、真实或明确标记为模拟的洪水面、对象预测、路网、源道路和资源 HDF；补齐资源距离风险字段与道路状态映射。`DemoDataset` 目前只审计源文件，没有创建这些原生图层。
2. 完成实时 AI 掩膜到对象级预测的可信桥接，或将比赛演示明确限定为预测结果回放；两者不能混称。
3. 在已授权的管理员 Windows 会话启动 MapGIS 官方宿主，加载一个完整案例并一键执行；逐步核对 MapGIS 图层、叠加数值、封路路线、资源可达性、七张真实截图和最终报告。检查 MapControl 截图是否实际包含地图内容。
4. 对至少一个行政区与一条绕行路径做独立数据复核，将运行日志及复核结果纳入比赛验收包。

当前结论：第五阶段集成代码已构建通过，**系统尚未达到“打开系统即能用内置数据完成完整演示”的最终验收目标**。
