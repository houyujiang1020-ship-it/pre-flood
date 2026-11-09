# MapGIS-FloodGuard 洪涝灾害智能分析与应急决策平台

> 仓库导航与数据准备说明见 [GitHub 仓库整理说明](docs/GITHUB_REPOSITORY.md)。训练数据、模型权重、实验输出和本机工具不纳入源码仓库。

本项目使用 Java + MapGIS SDK 构建桌面 GIS 工作台，以 FastAPI/PyTorch 提供遥感洪水检测服务。MapGIS `MapControl`、原生要素类、空间叠加、专题符号、网络分析和空间资源库承担 GIS 核心功能。演练输出是模拟或待核验结果，不能直接用于实际应急指挥。

## 系统架构与技术路线

`灾前/灾后影像 → AI 检测服务或预测结果回放 → MapGIS 对象级灾损专题 → 原生洪水面/人口/行政区叠加 → 风险分区 → 道路状态映射及原生路网绕行 → 资源推荐 → JSON/HTML 报告`。

- 桌面端：`app/mapgis-flood-desktop`，Java 21、JavaFX、MapGIS 官方 SDK/`MapControl`。
- AI 服务：`app/ai-service`，FastAPI 与 PyTorch。当前服务输出洪水掩膜；对象级 `flood_prediction.json` 通过独立输入进入 MapGIS 灾损模块。实时掩膜到对象级预测的桥接尚未完成，因此完整一键演练目前仅支持明确标记的 `REPLAY` 案例。
- 灾损分析：对象 JSON 导入 MapGIS HDF 要素类，分别显示正常/受淹建筑与正常/阻断道路，并支持对象点击查询。
- 风险评估：MapGIS SDK 投影、叠加与原生几何计算；人口风险只根据明确的洪水面图层计算，资源距离风险来自行政区 `resource_distance_risk` 字段。
- 应急调度：MapGIS `NetCls`/`NetAnalyse`、道路状态证据和空间资源点；阻断道路作为原生路障，输出路线与推荐报告。

## 第五阶段一键演练

主窗口新增案例管理、顶部“加载案例 / 开始分析 / 风险评估 / 路径规划 / 生成报告”工具栏、状态栏和综合态势面板。`DemoController` 按八步串行执行，每一步必须落盘证据；失败时停止并写入 `outputs/demo-runs/demo-*/demo-progress.json`。案例 JSON 位于 `outputs/scenarios`，删除案例仅删除清单，不删除源数据。

案例需提供影像、对象预测 JSON、MapGIS 行政区/人口/洪水面/原始道路/原生路网 URL、MapGIS 资源库清单、道路状态核查单、车辆与目标编号，以及风险字段名。加载案例后点击“开始灾害演练”。`REPLAY` 会标记为预测结果回放；`LIVE_AI` 在当前服务尚未产出对象级预测时会明确中止。

演练报告由 `ReportGenerator` 从各阶段持久化证据生成，目标文件为 `outputs/final-reports/report-*/FloodGuard_Final_Report.html`。真实工作台截图在宿主 GUI 成功渲染后自动写入 `outputs/screenshots/demo-*/`；比赛模式写入 `final_submission/screenshots/demo-*/`，七张必需图为首页、洪水检测、灾损、风险、路径、资源与报告，封路模拟另存补充图。截图采集失败会导致该演练步骤失败，不会生成占位截图。

`DemoDataset` 可核查仓库已有的离线影像、建筑、道路、人口、行政区和模拟资源素材，并输出 `outputs/demo-dataset-audit.json`。这些原始素材还缺少完整的同投影 MapGIS 原生数据集、明确洪水面、对象级预测及对应道路/资源证据，因此目前**不能仅凭内置素材完成无外部数据的一键全链路演示**。

## 构建与运行环境

需要已安装并授权的 MapGIS 官方桌面宿主及 SDK、Java 21、Maven 和 Windows 管理员会话。在仓库根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_mapgis_plugin.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_mapgis_host.ps1
```

截至 2026-10-04，构建通过，69 项测试通过，插件注册探针通过。宿主验证在管理员权限预检阶段停止，尚无本阶段真实 GUI 截图、MapGIS 原生运行结果或完整 `FloodGuard_Final_Report.html` 样本。比赛验收仍须在授权宿主中执行全流程，保存自动截图、报告和 `demo-progress.json`，并逐项核查地图、属性、路线与数值。

更完整的当前状态见 [第五阶段开发与验收记录](docs/STAGE5_INTEGRATION_20261004.md)；此前研究与数据限制见 `docs/PROJECT_PROGRESS_20261004.md` 和 `BLOCKERS.md`。

## 最终阶段交付适配

插件入口在创建地图组件前运行只读 `MapGISEnvironmentChecker`，写出 `outputs/environment_check.json`。SDK 文件可被静态确认；DLL 文件存在不等于依赖加载成功，许可证仅在官方宿主实际验证后才可判断。初始化异常会显示原因和检查建议，允许用户修复环境后重新打开。

`DemoDataset_Final/` 包含六项指定的模拟输入、洪水面/人口格网/行政区补充源文件和灾前灾后影像。它还没有转换并绑定到 MapGIS 原生路网、人口与资源数据库，因此 `06_scenario.json` 标记 `ready=false`；“比赛演示”会拒绝把未就绪素材展示为成功流程。`DemoScript.md` 提供五分钟讲解节奏。

`FloodGuard-Release/` 是经过文件白名单整理的发布暂存包，含 JAR、插件、配置、演示素材、说明和许可状态告知，不含训练缓存及无关日志。`FloodGuard.jar` 是宿主插件 JAR，并非独立桌面程序。最终通过项与缺口见 [final_acceptance_report.md](final_acceptance_report.md)。

## 第七阶段：提交门槛

`FinalEnvironmentCheck` 将 SDK、DLL 实际加载、许可证、MapControl 和插件状态写入 `submission/final_environment_report.json`；目前没有安全的官方只读授权查询，因此许可证保持 `UNVERIFIED`。`CompetitionScenario` 仅接受具有来源、SHA-256 与 MapGIS 原生 `gdbp://` 图层的正式案例。`ResultValidator` 将灾损、风险和路径 JSON 的数量、比例、长度与综合分数做交叉核对，写入 `submission/validation_result.json`；它不能替代独立空间复测。

评委模式记录 30/60/120/180/240 秒里程碑，并仅在真实 GUI 渲染后写入 `submission/screenshots/demo-*/` 的七张英文命名截图。`scripts/generate_final_checklist.py` 根据这些证据生成验收清单，当前记录见 [Final_Checklist.md](Final_Checklist.md) 和 [最终验收报告](docs/FINAL_ACCEPTANCE_REPORT.md)。本地提交包 `MapGIS-FloodGuard-Final/` 的清单标为未通过最终验收，`run.bat` 需要本机安装、授权并注册官方 MapGIS 宿主插件。

## AI 精度研究流程（2026-10-05）

新增训练集误报挖掘、类别感知裁剪、GIS 弱标签、双教师伪标签、Mean Teacher 烟测、固定阈值评估和一键实验入口。E4 原检查点与服务接口保持不变。训练集高误报前 20% 重采样候选在旧德国开发集上取得 macro IoU 0.165919（E4：0.160657），目前**仅是开发候选**；缺少独立四类测试真值，不能宣称最终精度提升或替换正式模型。结果、限制、复现方法见 [AI 精度实验报告](reports/ACCURACY_IMPROVEMENT_REPORT.md) 和 [训练流程说明](docs/MODEL_ACCURACY_PIPELINE.md)。
