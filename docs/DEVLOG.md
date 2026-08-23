# 开发日志

## 2026-08-23 — 工程初始化

- 问题：尚无工程骨架和环境事实。
- 处理：建立固定目录结构，开始环境审计与 MapGIS SDK 探测。
- 验证：目录和状态文件实际存在。

## 2026-08-23 — MapGIS 与上游探测

- 问题：最初常见路径探测未包含带版本号的安装目录；SpaceNet8 partial clone 无数据增长。
- 原因：本机安装目录为 `C:\Program Files\MapGIS 10`；Git partial-clone 对象获取路径网络异常。
- 解决：从运行服务的可执行路径反查安装根目录；SpaceNet8 改为浅克隆。
- 涉及：`docs/ENVIRONMENT_REPORT.md`、`docs/UPSTREAM_LOCK.md`。
- 验证：MapGIS 三项服务运行，Objects Java JAR 和三个自带 JRE 实际存在；MapGIS 上游 commit 已读取。

## 2026-08-23 — 开发工具链恢复

- 问题：Temurin JDK 8 的 GitHub MSI 下载停滞；系统缺少 Maven；默认 Maven 控制台误显示中文路径。
- 原因：GitHub 大文件通道速度异常；Maven 未提供适用的 winget 包；Java 默认采用 GBK。
- 解决：安装 Python 3.10 并创建 `.venv`；使用 Microsoft 官方 ZIP 部署 JDK 17；下载 Apache Maven 3.9.16 并校验 SHA-512；设置 `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8`。
- 涉及：`scripts/setup_python.ps1`、`scripts/setup_java.ps1`。
- 验证：Python 3.10.11、Java/Javac 17.0.20.1、Maven 3.9.16 均在中文项目路径实际运行成功。

## 2026-08-23 — SpaceNet8 工作树与 MapGIS 构建试验

- 问题：SpaceNet8 partial clone 已取得 commit/tree，但 blob 未完整下载，检出失败；MapGIS 旧上游首次 Maven 构建缺少 JavaFX 类。
- 原因：GitHub blob 通道异常；Microsoft JDK 17 不捆绑 JavaFX，而 2020 年上游源码依赖 JavaFX 及 `com.sun.javafx` 内部包。
- 解决：下载并展开 GitHub 官方 codeload `main` 归档，使用 partial clone 与 GitHub API 共同锁定 commit `30ca30c...`；JavaFX 构建问题保留为下一项真实兼容工作，不伪造构建成功。
- 验证：SpaceNet8 根 README、LICENSE、baseline README 均存在；MapGIS Maven 已成功进入源码编译阶段，失败点明确为 JavaFX 类路径而非 JDK/Maven不可用。

## 2026-08-23 — AI Service MVP

- 问题：官方 SpaceNet8 仓库未提供可直接使用的 baseline `best_model.pth`；历史运行环境携带重型 GIS 依赖。
- 原因：README 只给出用户训练后 checkpoint 的路径；baseline 将科研预处理、模型和 GIS 后处理放在同一 Docker 环境。
- 解决：建立独立 FastAPI/CLI 架构和明确标识的变化分析 fallback；不引入 GDAL/Fiona/GeoPandas；API 明示生产 checkpoint 未加载。
- 涉及：`app/ai-service`、`scripts/start_ai.ps1`、`scripts/run_tests.ps1`、`docs/API.md`。
- 验证：pytest 3 passed；Uvicorn 实际启动且 `/health` HTTP 200；中文路径推理结果文件存在且统计非零。

## 2026-08-23 — Java AI 客户端与风险引擎

- 问题：桌面端尚无可测试的 AI 服务调用边界，也缺少独立于 UI 的风险计算核心。
- 解决：新增 Java 17 Maven 模块、异步任务 DTO、HTTP 客户端、结构化异常和可配置风险评分器；测试使用本地 HTTP mock，并增加真实 Python 服务集成测试。
- 调试记录：首次从 PowerShell 传递 `-Dai.url=...` 时未加引号，被 Maven 解析成错误生命周期参数；改用单引号包裹完整 `-D` 参数后通过。
- 验证：Java 单元测试 3 passed；真实 Java→Uvicorn `/health` 集成测试 1 passed，Python 服务日志确认 HTTP 200。

## 2026-08-23 — MapGIS Java 21 插件适配

- 问题：JDK 17 编译本机 MapGIS JAR 时报告类文件版本 65 与编译器版本 61 不兼容。
- 原因：当前安装版 MapGIS 10 SDK 已使用 Java 21 构建，而独立业务核心仍以 Java 17 为最低运行版本。
- 解决：安装 Microsoft OpenJDK 21.0.12.1；采用双构建模式，核心测试继续使用项目 JDK 17，`mapgis-sdk` Profile 使用 JDK 21 和真实本机 SDK JAR；增加阴影插件包但排除宿主提供的 MapGIS/JavaFX。
- 涉及：`app/mapgis-flood-desktop/pom.xml`、`src/mapgis/java`、`scripts/build_mapgis_plugin.ps1`。
- 验证：MapGIS Profile BUILD SUCCESS，6 tests passed，插件 JAR 字节码版本 65。

## 2026-08-23 — 应急决策核心

- 实现：道路积水分级、不可通行边剔除、积水阻抗惩罚的 Dijkstra 安全路径；灾损汇总 DTO；基于真实输入值的 UTF-8 HTML 灾情报告。
- 验证：安全路线主动绕过阻断捷径；不可达场景抛出结构化错误；报告中文、数值和 HTML 转义测试通过。
