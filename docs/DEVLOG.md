# 开发日志

## 2026-08-27 — 真实数据、GPU 和桌面面板

- 官方 S3 下载配对与标注，灾前1300×1300/灾后约786×786，隔离科研环境按地理参考配准，不以拉伸代替配准。
- pip 的 download-r2 PyTorch 入口极慢，改用同一官方 download.pytorch.org CloudFront 文件；SHA256 与官方索引9b22d6d98aa56f9317902dec0e066814a6edba1aada90110ceea2bb0678df22f一致。
- RTX4050实际完成烟测，checkpoint保存重载成功，IoU0如实保留。最终推理环境增加纯PyTorch后端，不带Rasterio。
- 插件新增影像选择、输出选择、非阻塞任务进度、取消等待、预览及错误信息。未经空间参考验证的PNG不自动加载地图。编译通过，UI运行仍待授权。
- 原授权检测错误地强制 .lic；修为云开发参数并保留官方校验。原生日志混合GBK/UTF8导致失败识别漏报，改为Python保留原始字节，双编码匹配，实测准确返回失败。
- 本机找到 MapGIS_Java_Api 10.7.10.10 完整Javadoc，后续空间化/网络分析优先依据该文档和JAR编译验证。

## 2026-08-27 — 资源推荐与输入健壮性

- 新增 ResourceDispatcher：按资源类型、容量和可达性过滤，再按预计时间排序；路线提供器可替换，当前不冒充 MapGIS 网络分析。
- 修复道路输入允许负距离、零速度、NaN 和无效标识的问题；灾损面积拒绝非有限数值。
- E2E 增加生成失败、端口占用和子进程提前退出检查，避免误测其他服务。
- 实测总回归退出码 0：Python 3，Java 17 核心 8，HTTP 集成 1，Java 21 SDK 构建测试 8，全部通过。

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

## 2026-08-23 — MapGIS Java 宿主启动试验

- 命令：使用安装目录 JRE 21、Program 和 `lib` 全类路径启动官方 `DesktopLauncher`。
- 结果：官方启动器、JavaFX 21 和 UI 字体成功初始化，随后在产品授权阶段报告目标 `.lic` 缺失，并且硬 Key 验证失败。
- 处理：未把“洪涝插件加载”或“AI 结果加载至 MapGIS”标成完成；授权细节已写入 `BLOCKERS.md`，增加补齐许可后的宿主验证脚本。

## 2026-08-23 — 自动化跨进程 E2E

- 实现：可重复生成中文文件名演示影像；PowerShell 隐藏启动/健康等待/可靠关闭 AI 服务；Java 从真实 HTTP 服务提交任务并校验输出文件和统计结果。
- 验证：`.\scripts\run_e2e.ps1` BUILD SUCCESS，1 integration test passed；没有遗留 Uvicorn 进程。
