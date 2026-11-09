# 第四阶段：MapGIS 原生应急路径与资源调度

日期：2026-10-04。当前状态：**SDK 代码和 GUI 入口已编译；MapGIS 宿主运行验收未完成**。

## 已实现

- `EmergencyRoutePlanner` 使用 MapGIS `NetCls` 和 `NetAnalyse.pathAnalyse` 求封路前、封路后两条路径。按边的米制几何长度设置双向成本：正常 ×1、积水 ×10、高风险 ×50、阻断 ×999999；阻断边还作为 MapGIS `NetBarrier` 排除。原网络成本在 `finally` 中恢复。分析会读回设置的成本，并比对 SDK 返回的路径成本与逐边成本；不一致就停止输出“优化路线”。
- 风险倍率是选路惩罚，不等于实测车速。报告时间按路线实际长度和 GUI 明示的演练速度换算；不包含实时交通、信号灯或涉水速度实测。
- `MapGisRouteThematicWriter` 将蓝色原始路线、绿色优化路线、红色风险道路、黑色阻断道路写成四个 MapGIS HDF 原生线要素类。图层支持工作台缩放和点击查询，查询对象保存证据。
- `ResourceManager` 将救援车辆、医疗点、避难点作为 MapGIS HDF 原生点要素管理，支持添加、修改、删除、查询和再次打开资源库。车辆使用 SVG 车辆标记，医疗点使用十字标记，避难点使用蓝色定位标记。资源坐标必须与所选路网同一米制投影，并在 25 m 内绑定 MapGIS 网络节点。
- `EmergencyDispatchPanel` 在“应急路径”“资源调度”“应急调度”菜单中提供路径规划、资源管理、救援模拟三页。可点击风险专题区域，按该区域中心附近的路网节点规划“车辆 → 灾害区域 → 医疗点/避难点”。资源推荐按原生路网可达性及动态成本排序，并显示长度、估计时间和路线风险。
- 救援模拟以临时 MapGIS 车辆点沿优化路线节点移动，保存 `rescue-simulation.log`，结束时清理临时标记。模拟结果不是实际调度指令。

## 道路状态输入契约

GUI 的“加载道路状态证据”读取 JSON，并用 `MapGisRoadNetworkMapper` 将**原始道路要素 ID** 映射到所选 `NetCls` 的边 ID。不能只凭 AI 对象坐标做最近边猜测。范例中的 URL 和 ID 是占位符，必须替换为本机真实 MapGIS 数据，并为每条状态提供核查依据。

```json
{
  "network_url": "<当前 MapGIS NetCls URL>",
  "roads_url": "<该路网登记的原始道路 SFeatureCls URL>",
  "network_edge_count": 1234,
  "unlisted_status": "NORMAL",
  "unlisted_evidence": "未列出路网边的正常通行核查记录编号",
  "roads": [
    {"source_feature_id": "101", "status": "FLOODED", "evidence": "现场积水核查记录编号"},
    {"source_feature_id": "102", "status": "HIGH_RISK", "evidence": "风险评估与人工核查记录编号"},
    {"source_feature_id": "103", "status": "BLOCKED", "evidence": "封路通知编号"}
  ]
}
```

未列入的网络边只有在清单声明 `unlisted_status=NORMAL`、提供全网核查依据并核对当前网络边总数后才按正常道路处理。允许的 `status` 值为 `NORMAL`、`FLOODED`、`HIGH_RISK`、`BLOCKED`。重复映射、缺少依据、路网不匹配和无源要素映射均拒绝计算。加载更新后的道路状态时，已有路线图层立即失效；在车辆和目标已选定的情况下自动重算。

## 运行输出

在工作台证据目录的 `route-<UUID>` 下生成 `route_report.json`、`route-thematic-manifest.json`、四类原生路线要素所在的 HDF。运行资源推荐后生成 `resource-recommendations.json`；运行模拟后生成 `rescue-simulation.log`。`route_report.json` 包括起点、目标、距离（米）、估计时间（分钟）、风险级别、阻断道路避让数、经过边数、原始/优化边序列、输入来源与演练速度。工作台截图按钮会保存实际窗口 PNG 和日志。

## 本次验证与未完成事项

- `scripts/build_mapgis_plugin.ps1` 通过，63 项 JUnit 测试全部通过，插件注册探针通过。详见 [emergency-dispatch-build-20261004.log](emergency-dispatch-build-20261004.log)。这只证明 Java 与已安装 SDK 符号兼容，不证明原生路径在实际数据上通过。
- 当前 Windows 会话不能通过官方 MapGIS 宿主的管理员权限前置检查，见 [emergency-dispatch-host-20261004.log](emergency-dispatch-host-20261004.log)；现有数据中也没有可直接用于本模块的真实道路状态核查 JSON、车辆/医疗点/避难点清单和风险区到路网节点的验收绑定。因此**尚未生成真实 `route_report.json`、封路前后截图、资源地图截图或模拟日志实例**。
- 下次验收须在已授权、可启动的 MapGIS 桌面环境中，以真实 `NetCls` 和对应源道路要素类验证最小成本模式确实采用动态权值；核对分路段长度、成本、路障排除和单行方向。若 MapGIS 返回成本与逐边成本不一致，当前代码会拒绝路线，而不会静默退回 Java 路径算法。
- 资源推荐当前依据路网可达性和路线风险；未接入实时交通、车辆班次、医疗床位实时接口，也未对现场安全作保证。救援速度是显式输入的演练值。
