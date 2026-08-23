# MapGIS Flood Desktop Core

该模块包含可测试的 Java 业务层、AI HTTP Client，以及基于本机 MapGIS 10 SDK 真实接口编译的插件命令和结果图层加载器。

## 构建

- Java 17 核心测试：`mvn test`
- MapGIS 10 Java 21 插件：`scripts\build_mapgis_plugin.ps1`
- 产物：`target\mapgis-floodguard-plugin.jar`

命令读取 `floodguard.pre`、`floodguard.post`、`floodguard.output`，以及可选的 `floodguard.ai.url`，完成异步推理并把洪涝掩膜加载到当前二维地图。
