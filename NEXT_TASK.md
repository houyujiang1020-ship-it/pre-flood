# 下一步任务

已完成工程骨架、环境、上游锁定、AI fallback 服务、Java/Python 通信、风险与安全路径核心，以及基于本机真实 SDK 的 MapGIS Java 21 插件编译和打包。

最后一次运行 `.\scripts\run_tests.ps1`：Python 3 passed；Java 17 核心 6 passed；MapGIS Java 21 Profile 6 passed并生成 `app\mapgis-flood-desktop\target\mapgis-floodguard-plugin.jar`。下一步把插件加入 MapGIS Ribbon 宿主配置并实际加载；随后把推理结果、灾损统计、安全路线和 HTML 报告串为 E2E Demo。SpaceNet8 官方 checkpoint/官方最小样本仍需继续获取或执行 smoke training。

继续工作前依次阅读：`README_CN.md`、`PROJECT_STATUS.md`、`NEXT_TASK.md`、`BLOCKERS.md`、`docs/DEVLOG.md`。
