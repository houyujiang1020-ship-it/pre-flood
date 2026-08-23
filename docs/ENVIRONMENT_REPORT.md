# 环境审计报告

审计时间：2026-08-23（Asia/Shanghai）

## 已验证硬件与系统

- Windows：64 位，构建号 26200（系统接口产品名返回 Windows 10 Home China）
- CPU：AMD Ryzen 7 7735H，8 核 16 线程
- 内存：15.25 GB
- GPU：NVIDIA GeForce RTX 4050 Laptop GPU，6141 MiB 显存
- NVIDIA 驱动：566.26；驱动报告最高 CUDA 12.7
- C 盘剩余空间：约 88.1 GB

## 工具链

- Git 2.53.0.windows.3：可用
- 系统 Python 3.13.11：可用，但不作为 SpaceNet8 主环境
- Python 3.10.11：已通过 winget 安装；项目 `.venv` 已创建并验证
- Java：项目本地 Microsoft OpenJDK 17.0.20.1，`java`/`javac` 均已验证
- Maven：项目本地 Apache Maven 3.9.16，发行包 SHA-512 已按官方校验文件验证
- MapGIS 自带 JRE：Java 8u144、Temurin 17.0.13、OpenJDK 21.0.11；均为运行时，不含 `javac`
- MapGIS-Desktop-Java 官方源码的 Maven 编译目标：Java 8（由各模块 `pom.xml` 的 source/target 1.8 验证）

## MapGIS

- 安装根目录：`C:\Program Files\MapGIS 10`
- 核心 Objects Java JAR 已发现：`mapgis_geoobjects.jar`、`mapgis_geodatabase.jar`、`mapgis_geomap.jar`、`mapgis_geoanalysis.jar`、`mapgis_pluginengine.jar` 等
- 服务：IGServer、DataStorage、Tile Storage 均为 Running
- 注册表存在 MapGIS 开发者授权记录；报告不复制序列号、注册码或签名
- 后续 API 仅从上述 JAR、官方源码、Sample 和 Documentation 中提取并以编译验证

## 结论

硬件可支持 6 GB 显存的小批量训练/推理。Python、JDK 和 Maven 已由可重复脚本配置；Java 构建统一强制 UTF-8，中文项目路径已通过 Maven 版本启动检查。
