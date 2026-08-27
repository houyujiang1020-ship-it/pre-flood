# 下一步任务

2026-08-27：资源推荐业务层与输入校验已实现，总回归 Python 3 / Java 17 8 / HTTP 1 / Java 21 8 全通过。云开发授权已识别但验证失败，见 BLOCKERS.md 更正。后续优先接入官方 MapGIS 网络分析实现路线提供器、完成官方 SpaceNet8 样本和训练链路，并完善桌面交互。不要把自写路由和合成影像当成参赛验收结果。

已完成工程骨架、环境、上游锁定、AI fallback 服务、Java/Python 通信、风险与安全路径核心，以及基于本机真实 SDK 的 MapGIS Java 21 插件编译和打包。

最后一次联合回归：Python 3 passed；Java 17 核心 6 passed；跨进程真实推理 E2E 1 passed；MapGIS Java 21 Profile 6 passed并生成 `app\mapgis-flood-desktop\target\mapgis-floodguard-plugin.jar`。MapGIS 宿主实际启动已到达授权验证阶段，但缺少匹配许可，见 `BLOCKERS.md`。下一步继续把灾损统计、安全路线和 HTML 报告串入演示输出，并完成下载/训练脚本；许可补齐后立即执行宿主插件可见加载与结果图层测试。

继续工作前依次阅读：`README_CN.md`、`PROJECT_STATUS.md`、`NEXT_TASK.md`、`BLOCKERS.md`、`docs/DEVLOG.md`。
