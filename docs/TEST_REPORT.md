# 测试报告

## 2026-08-23 — AI Service

- 命令：`.\scripts\run_tests.ps1`
- 结果：3 passed，0 failed，0 warnings
- 用时：0.52 秒（pytest 报告）
- 覆盖：health、model info、异步 inference、真实输出文件、输入变化统计、错误路径、中文输入/输出路径。
- HTTP 启动验证：Uvicorn 监听 `127.0.0.1:8765`，`GET /health` 返回 HTTP 200；随后正常关闭。
- 说明：当前变化分析后端已通过，但 SpaceNet8 生产 checkpoint 尚未加载，因此“SpaceNet8 最小真实推理”仍未勾选。
