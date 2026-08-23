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
