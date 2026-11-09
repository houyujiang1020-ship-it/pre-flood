# FloodGuard 桌面工作台（2026-10-04）

## 本次实现

`FloodGuardMainWindow` 已作为现有 MapGIS Ribbon 命令的主窗口。布局为左侧七项功能菜单、中间官方 `com.zondy.mapgis.controls.MapControl`、右侧分析指标及底部持续日志。官方地图组件加载 GeoTIFF 栅格及 MapGIS SDK 可连接的矢量 URL。数据管理页可以加载底图、遥感影像、洪水结果、建筑/道路灾损和人口分布图层。地图工具栏提供全图、放大、缩小及证据保存。

洪水检测沿用现有 FastAPI/Java/MapGIS 空间化流程。灾损分析沿用 MapGIS 原生相交查询，受淹建筑显示为“候选”，不会充当确认损毁。道路总长从米制投影道路实体图层的 MapGIS 几何计算；无法确认投影时显示“待投影核验”。风险评估仅在五项数值输入齐全时调用现有 `RiskCalculator`。人口参考估算可读取已有 Gate 5 证据，界面明确标注尚待 MapGIS 原生复算。路径与资源页复用原生路网、阻断避让和容量分配面板。系统报告入口可保存当前截图、日志和图层/指标 JSON；完整业务报告由调度面板导出。

主窗口把分析状态、模型状态、路线计算及异常持续写入日志。点击“保存验收截图”会在 `runtime/desktop-evidence/workspace-<时间>/` 写入 `workspace.png`、`run.log` 和 `evidence.json`。JSON 保留图层名称、URL、显示状态、指标和来源。截图只记录实际可见窗口，不自动认定模型精度或业务门禁通过。

## 验证结果

- `scripts/build_mapgis_plugin.ps1`：SDK 56 项测试通过，插件 JAR 构建及官方 SDK 注册探针通过。
- `python -m pytest -q tests/test_desktop_config.py tests/test_demo_lifecycle.py`：9 项通过。
- `scripts/verify_mapgis_host.ps1`：当前 Windows 会话非管理员，在启动/授权检查前按预检规则停止。故主窗口实际渲染、图层叠加、按钮联动与截图仍缺现场证据。本次未生成声称已通过的 GUI 截图。

## 现场验收

在已授权账户的管理员 PowerShell 中运行 `scripts/start_demo.ps1`。启动后 Ribbon 中选择“洪涝应急决策平台”，逐项核验地图加载、洪水检测、实体相交、道路长度、风险输入、调度和报告。每项运行成功后点击“保存验收截图”，核对同目录 JSON 与日志，并为 Gate 5/9 补齐要求的业务截图及签字记录。结束时用 `scripts/stop_demo.ps1` 关闭本项目启动的进程。

当前研究模型的独立精度和真实资源台账仍需单独验收，GUI 可运行不改变 `production_ready=false` 与现有 4/9 门禁状态。
