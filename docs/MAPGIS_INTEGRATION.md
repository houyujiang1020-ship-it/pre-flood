# MapGIS 集成与验证边界

本机 SDK：MapGIS10.7.10.10，Program 下 JAR。Javadoc 位于 `Program/MapGIS_Java_Api`，必须与 JAR 一起查证 API。插件 Java21 编译，MapGIS SDK 不随 shaded JAR 打包。

## 已编译接口

- FloodInferenceCommand → FloodMainPanel：通过 ICommand 入口显示影像选择、异步任务、进度、取消等待、原始统计及预览。
- MapGisResultLayerLoader：活动 IMapContentsView → MapControl → Map → RasterLayer.connectData/append/refreshWnd。
- MapGisRasterSpatializer：RasterDataset.open/convertTo(GTiff)/setRange/setSref，保存后重开检查。仅支持同尺寸、北向上、无旋转参考网格，不覆盖源文件；仍待宿主实际验证。不能用同尺寸推断灾前灾后地理网格一致。
- MapGisNetworkRouter：真实 NetAnalyse、PathWgtParam、NetFlagList、NetBarrierList、pathAnalyse。使用已经登记且单位为分钟的正向/反向/节点网络权；阻断边转为原生障碍。调用失败不回退自写Dijkstra，返回路线若包含阻断边直接拒绝。

路由器需要已打开的 NetCls、业务节点到网络节点ID映射、道路状态对应的阻断边集合，以及明确的网络线性单位换算。经纬度网络不能简单用固定系数换算公里，应先由 MapGIS 投影。动态道路权更新、模型结果与路段匹配、空间统计及GUI业务联动仍未完成。

## 必须完成的实际验收

1. 官方开发启动器成功验证授权，打开二维地图。
2. 在官方插件管理中加载洪涝JAR，确认命令出现并能打开面板。
3. MapGIS 对齐官方灾前/灾后空间网格，完成AI推理。
4. 结果空间化后验证范围、坐标系、像素位置，与原图叠加。
5. 用小型已知路网，验证阻断绕行、单向边、不可达、阻抗变化与距离单位。
6. 再验证真实灾损叠加与报告。未完成这些步骤不得宣称完整E2E通过。

## 授权诊断

`scripts/verify_mapgis_host.ps1 -Mode Developer` 采用官方 --developer 和 JavaFX 参数，原始日志保存到 logs/mapgis-host。支持GBK/UTF8错误识别。2026-08-27实测返回 authorization_failed，退出码3；不修改许可、不绕过校验。进程存活不构成通过。宿主还报告 Program Files 下日志目录写权限问题，须用官方管理员启动流程/授权管理确认。
