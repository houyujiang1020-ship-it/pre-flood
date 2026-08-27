# Windows部署

本机验证：Windows11、Python3.10.11、RTX4050 Laptop6GB、驱动566.26、PyTorch2.5.1+cu121，Java17核心与Java21 MapGIS插件。Maven3.9.16。版本实测记录见ENVIRONMENT_REPORT.md和依赖锁。

按照README_CN.md建立.venv和.venv-training。setup_torch从官方CloudFront下载2.45GB wheel并校验官方SHA256；建议至少8GB空闲空间用于下载和解压。训练和推理各装一次PyTorch，安装文件缓存共用，科研GIS依赖隔离。

MapGIS Program必须包含pluginengine/geomap/ui_controls/geodatabase/geoobjects/geoanalysis JAR、官方Java21运行时和相应原生DLL。禁止用不匹配的其他产品许可代替。build_mapgis_plugin默认本机JDK21目录，迁移时通过-Jdk21和-MapGisProgram参数指定新位置。

云开发授权：通过安装目录Program/desktop-developer.bat官方启动流程操作；它要求管理员权限。不要导出/粘贴注册表密钥到聊天。2026-08-27本机识别云开发授权但验证失败，Program Files日志目录还出现权限错误。需在官方授权管理完成有效性确认，不能由本项目修改校验逻辑解决。

验证命令verify_mapgis_host.ps1只做只读诊断并保留原始混合编码日志；code3是授权失败，code2是仍需人工确认，均不是通过。
