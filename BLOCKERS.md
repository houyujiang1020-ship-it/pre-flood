# 外部阻塞项

## MapGIS Objects Java 21 运行授权

### 当前需要的外部操作

请在本机通过官方 `C:\Program Files\MapGIS 10\Program\desktop-developer.bat` 管理员启动流程，确认云开发授权登录、有效期及本机/产品范围；如仍失败，需在官方授权管理或厂商支持渠道修复。工程侧已确认注册表有授权信息，但不能据此判断许可有效。无需向聊天发送密钥或授权文件内容。

2026-08-27最新完整启动：AI CUDA就绪，DesktopLauncher --developer --custom-ui进入授权阶段后明确失败。脚本已清理全部本次进程。用户确认官方宿主授权成功后，执行 `scripts/start_demo.ps1` 继续插件、空间化、网络与完整GIS业务验收；其余未完成项见PROJECT_STATUS，不宣称自动变成已完成。

### 2026-08-27 更正（以下旧记录仅保留排查历史）

已发现下载目录的开发授权包及当前用户 Developer 注册表授权。官方 `desktop-developer.bat` 使用 `--developer`；实测加此参数后宿主识别“云开发授权”，但验证仍失败。不能再把缺少 `.lic` 当作所有模式的阻塞原因。`verify_mapgis_host.ps1` 已移除错误的 .lic 前置检查，默认 Developer 模式，记录 stdout/stderr，并明确进程存活不等于授权通过。下一步需通过官方开发启动脚本、管理员权限和云授权状态排查；不得修改授权校验或密钥。

- 状态：SDK JAR 可用且插件已编译，但 Java Ribbon 宿主实际启动时授权验证失败。
- 宿主报告的期望文件：`C:\Program Files\MapGIS 10\license\1F4C6E79FEEEEF2C4CAA1B45FBAABDC0.lic`
- 当前事实：`C:\Program Files\MapGIS 10\license` 中未发现该许可证文件；宿主转而使用“硬Key授权”并验证失败。
- 需要提供：与当前 MapGIS 10.7.10.10 / Objects Java 产品匹配的有效软授权 `.lic`，或连接并激活对应硬件 Key。
- 放置位置：按 MapGIS 宿主提示放到 `C:\Program Files\MapGIS 10\license\`；许可证必须匹配本机和产品，不能用其他产品的许可替代。
- 补齐后执行：`.\scripts\verify_mapgis_host.ps1`，随后完成插件可见加载和结果图层显示测试。

## SpaceNet8 生产模型资源

- 状态：官方仓库没有附带 baseline `best_model.pth`，当前服务使用明确标识的输入驱动变化分析 fallback。
- 官方样本已下载两组并校验，数据不再是阻塞项。仍需训练并评估 checkpoint，不能把烟测当生产模型。
- 推荐位置：`data\spacenet8\sample` 与 `models\checkpoints\spacenet8\best_model.pth`。
- 补齐后执行：后续的 `scripts\train_smoke.ps1` 或 `scripts\download_models.ps1`，再切换生产推理后端。
