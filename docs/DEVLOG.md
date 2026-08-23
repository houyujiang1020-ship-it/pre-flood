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
