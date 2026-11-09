# 灾损专题图开发记录（2026-10-04）

## 输入契约

桌面“灾损分析”页可选择 `flood_prediction.json`。若启动参数 `-Dfloodguard.prediction=<绝对路径>` 指向现有文件，首次进入该页时自动加载；否则可点击“加载 flood_prediction.json”。格式为：

```json
{
  "crs_wkt": "<MapGIS 可解析的米制投影 WKT1>",
  "objects": [
    {
      "object_id": "B-001",
      "type": "building",
      "geometry": {"type":"Polygon","coordinates":[[[500000,3500000],[500020,3500000],[500020,3500020],[500000,3500020],[500000,3500000]]]},
      "damage_probability": 0.92,
      "flood_status": "flooded"
    }
  ]
}
```

`type` 接受 `building`、`road`。建筑的 `flood_status` 接受 `normal`、`not_flooded`、`flooded`；道路接受 `normal`、`blocked`。道路受淹不自动等于阻断，必须有明确 `blocked` 状态。概率必须在 `[0,1]`，编号不得重复，建筑只接受闭合 Polygon，道路只接受 LineString。缺失米制投影 WKT 时拒绝面积计算，不把经纬度当米。示例输入位于 `app/mapgis-flood-desktop/src/test/resources/flood_prediction.fixture.json`，仅为合成测试数据，不能充作真实灾情或竞赛验收。

受灾等级为展示分档：正常对象“无”，其余对象概率 `<0.5` 为“低”、`0.5–<0.8` 为“中”、`≥0.8` 为“高”。该分档不表示模型精度通过或现场核验完成。

## MapGIS 实现

`DamagePrediction` 先完成纯 Java 输入契约校验。`MapGisDamageThematicImporter` 用 MapGIS Local HDF 建立四个 `SFeatureCls`：未受淹建筑、受淹建筑、正常道路、阻断道路。几何由 MapGIS `Geometry.fromGeoJson` 读取；建筑 `GeoPolygon.calArea()`、道路 `GeoLine.calLength()` 计算米制投影下的面积/长度。每个要素保留编号、类型、状态、概率、等级、面积或长度、坐标。坐标是 MapGIS 几何外包矩形中心，并在属性窗明确标注。

每个原生 `VectorLayer` 使用 MapGIS `SimpleRenderer`：建筑 `FillSymbol` 为绿色 `#2E7D32` / 红色 `#D32F2F`，道路 `LineSymbol` 为灰色 `#757575` / 红色 `#D32F2F`，宽度分别为 1.5 / 4。通过 MapGIS `MapControl.identifySelections` 点击专题对象后读取原生要素属性。

## 输出证据

实际导入成功后，`runtime/desktop-evidence/damage-<UUID>/thematic-manifest.json` 保存输入 SHA-256、CRS、MapGIS HDF 路径、四类数量、图层 URL、符号约定及未完成的核验状态。每次点击对象另存 `selected-object-<UUID>.json`。主窗口会在图层加载及对象点击后调用现有截图功能，保存 `workspace.png`、`run.log`、`evidence.json`；其中包含专题 manifest 路径。

## 本次验证与限制

- `scripts/build_mapgis_plugin.ps1`：Java/MapGIS SDK 编译、60 项测试、插件注册探针通过。
- 纯 Java 输入样例覆盖四类分类；对受淹道路误推断阻断、非米制 CRS、非法概率等输入执行拒绝测试。
- 当前 Windows 会话不能完成真实 MapGIS 宿主验收。尝试独立启动官方 `MapControl` 时 `mapgis_geoobjects.dll` 初始化失败，详见 `runtime/damage-probe.log`；此前宿主启动脚本也在管理员权限预检处停止。因此目前没有真实专题地图截图，也不能声称颜色渲染、对象点击或 HDF 导入已在宿主中验证。

现场验收需在已授权管理员会话内启动项目桌面，加载真实 `flood_prediction.json`，检查四类颜色与线宽、点击属性、四类数目、面积/长度和坐标，再归档自动生成的截图及 JSON。该工作不改变现有 `production_ready=false` 和竞赛就绪度 4/9。

