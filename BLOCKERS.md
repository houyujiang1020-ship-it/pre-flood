# 外部阻塞项

## MapGIS Objects Java 21 运行授权

### 2026-08-27 更正（以下旧记录仅保留排查历史）

已发现下载目录的开发授权包及当前用户 Developer 注册表授权。官方 `desktop-developer.bat` 使用 `--developer`；实测加此参数后宿主识别“云开发授权”，但验证仍失败。不能再把缺少 `.lic` 当作所有模式的阻塞原因，也不能用现有 `verify_mapgis_host.ps1` 的 `.lic` 前置检查判断开发授权有效性。下一步需通过官方开发启动脚本、管理员权限和云授权状态排查；不得修改授权校验或密钥。

- 状态：SDK JAR 可用且插件已编译，但 Java Ribbon 宿主实际启动时授权验证失败。
- 宿主报告的期望文件：`C:\Program Files\MapGIS 10\license\1F4C6E79FEEEEF2C4CAA1B45FBAABDC0.lic`
- 当前事实：`C:\Program Files\MapGIS 10\license` 中未发现该许可证文件；宿主转而使用“硬Key授权”并验证失败。
- 需要提供：与当前 MapGIS 10.7.10.10 / Objects Java 产品匹配的有效软授权 `.lic`，或连接并激活对应硬件 Key。
- 放置位置：按 MapGIS 宿主提示放到 `C:\Program Files\MapGIS 10\license\`；许可证必须匹配本机和产品，不能用其他产品的许可替代。
- 补齐后执行：`.\scripts\verify_mapgis_host.ps1`，随后完成插件可见加载和结果图层显示测试。

## SpaceNet8 生产模型资源

- 状态：官方仓库没有附带 baseline `best_model.pth`，当前服务使用明确标识的输入驱动变化分析 fallback。
- 需要提供或生成：官方 SpaceNet8 数据样本及通过 baseline 训练产生的 checkpoint。
- 推荐位置：`data\spacenet8\sample` 与 `models\checkpoints\spacenet8\best_model.pth`。
- 补齐后执行：后续的 `scripts\train_smoke.ps1` 或 `scripts\download_models.ps1`，再切换生产推理后端。
