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
