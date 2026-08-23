# 测试报告

## 2026-08-23 — AI Service

- 命令：`.\scripts\run_tests.ps1`
- 结果：3 passed，0 failed，0 warnings
- 用时：0.52 秒（pytest 报告）
- 覆盖：health、model info、异步 inference、真实输出文件、输入变化统计、错误路径、中文输入/输出路径。
- HTTP 启动验证：Uvicorn 监听 `127.0.0.1:8765`，`GET /health` 返回 HTTP 200；随后正常关闭。
- 说明：当前变化分析后端已通过，但 SpaceNet8 生产 checkpoint 尚未加载，因此“SpaceNet8 最小真实推理”仍未勾选。

## 2026-08-23 — Java 桌面核心与跨进程联调

- Java 单元测试：3 passed，0 failed，覆盖 AI HTTP 客户端、中文路径 JSON 序列化、风险评分与风险等级。
- 真实联调：启动 Python Uvicorn 后执行 `RealAiServiceIT`，Java 请求 `http://127.0.0.1:8765/health` 返回 HTTP 200；1 passed，0 failed。
- 联合回归入口：`scripts/run_tests.ps1` 依次执行 Python 与 Java 测试。
- 边界：当前完成的是可运行的 Java 服务调用核心，不代表 MapGIS 插件已完成加载。

## 2026-08-23 — MapGIS SDK 编译与决策业务回归

- 联合命令：`.\scripts\run_tests.ps1`
- Python：3 passed，0 failed。
- Java 17 核心：6 passed，0 failed；新增洪灾安全路径、不可达路径、HTML 报告真实数值和 HTML 转义测试。
- MapGIS Java 21：使用本机 `mapgis_pluginengine.jar`、`mapgis_geomap.jar`、`mapgis_ui_controls.jar` 编译 12 个源文件，6 tests passed，生成 `target\mapgis-floodguard-plugin.jar`。
- 产物核验：插件命令、MapGIS 结果图层加载器和 Jackson JSON 类均在 JAR 内；命令字节码 major version 65，与本机 MapGIS Java 21 SDK 一致。
- 边界：SDK 编译和打包已真实完成；仍需在 MapGIS Ribbon 宿主中完成可见加载后，才能勾选“洪涝插件加载”和“AI 结果加载至 MapGIS”。

## 2026-08-23 — 跨进程推理 E2E

- 命令：`.\scripts\run_e2e.ps1`
- 流程：生成中文路径灾前/灾后演示影像 → 隐藏启动 Uvicorn → 轮询 health → Java 提交异步推理 → 轮询 job → 校验结果掩膜存在和洪水像素统计非零 → 关闭服务。
- 结果：`RealAiServiceIT` 1 passed，0 failed；总用时约 8 秒。
- 输出：`data\outputs\e2e` 下产生实际输入驱动的 mask、preview、分类 mask 和统计文件。
- 边界：MapGIS 宿主内图层加载仍被 Objects Java 授权阻塞，因此这条测试没有伪称完整 MapGIS E2E。
