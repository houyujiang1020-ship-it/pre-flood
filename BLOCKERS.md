# 外部阻塞项

## 2026-10-10 管理员宿主新证据（当前）

用户在管理员 PowerShell 中运行 `scripts/verify_mapgis_host.ps1`，`logs/mapgis-host/20261010-193316-021.stdout.log` 明确记录官方 MapGIS 10 Java 21 宿主的云开发授权验证成功。脚本码 2 是 10 秒诊断后主动停止、要求人工继续核验，不是授权失败。当前 Codex 执行进程仍非管理员；本次未加载 FloodGuard 自定义 UI、NetCls 或完成 MapControl/NetAnalyse 验收。下一步优先在同一管理员账户持续启动项目宿主并提供同版本道路、网络、资源及案例证据，详见 `reports/dev-continuation-20261010/30_p007_handoff.md`。

## 2026-09-26 当前宿主与独立测试阻断

- 官方 Louisiana-West public test 已到位并完成 406 对一次性无标签推理，但发布包没有 GeoJSON 真值；因此仍不能计算独立 IoU/F1/precision/recall。该 test 已使用并永久禁止训练、校准和选模。协议状态保存在 `experiments/external-test-protocol-20260926/protocol-readiness.json`。
- 本轮只读运行 `scripts/verify_mapgis_host.ps1`，在启动 MapGIS 或执行授权检查前即由 `require_administrator()` 拒绝：当前 Codex Windows 会话不是管理员。没有产生 GUI 验收证据，也没有把进程存活误记为授权通过。
- MapGIS 10 安装目录存在，SDK/插件构建链通过；Gate 5 仍需要在已授权 Windows 账户的管理员会话内完成七张真实截图、正式空间复算和业务签署。
- 仍缺新的、带四类真值且与全部开发/已用 test 区域独立的数据，不能满足 `independent_model_accuracy` 或将模型设为 `production_ready=true`。

## 2026-09-12 Gate 5 Phase 2 剩余阻断（当前）

- Community 与 population 数据缺失已解除：BKG Dernau Gemeinde 和 Destatis Zensus 2022 100m 格网均已下载、校验、固定来源与哈希。
- 剩余正式 GIS 阻断：当前自动化环境无 native app binding，不能运行授权 MapGIS 的 community/population/实体空间复算、专题表达和七张 GUI 截图；人工证据清单已生成。
- 剩余风险阻断：现有 RiskCalculator 还需要有正式定义的 flood 指标、MapGIS 验证的道路可达性和真实医疗可达性。缺失值不能置0，故 risk score/level 保持 null。
- Gate 5 validator 退出2，readiness 保持4/9。`runtime/acceptance/gate5-phase2-20260912-01/gui-evidence-manifest.json` 明确为 pending。

## 2026-09-12 Gate 5 阻断（Phase 1 历史）

- 固定 Germany `0_41_59` 范围没有真实/赛事认可社区边界和带许可、日期的人口数据，风险评分不可计算。
- SpaceNet8 只提供对象级 flooded 属性，没有连续洪水面或道路封闭观测；这些字段保持 N/A，不能推导补齐。
- 当前 Windows Computer Use 暴露的 native app 列表为空且无 native `getApp` 接口，未能执行实际 MapGIS GUI 核验。Gate 5 保持 BLOCKED，readiness 保持 4/9。
- 可复跑入口：`.\scripts\validate_gate5.ps1 -RunDirectory runtime\acceptance\gate5-gt-20260912-01`；补齐输入和真实 GUI 证据前预期退出码为2。

## 2026-09-12 13:37 人工审查状态

Germany审查工作流的工程阻塞已解除：197项预览及overlay生成成功，真实清单474个影像SHA256校验通过，旧20项保持兼容。业务阻塞仍是177项需要人工逐项决定；工具不会自动接受、冻结split或训练。

## 2026-09-12 当前阻塞（优先于下方历史）

1. GN训练与API技术链已贯通，但三个Germany 10/4小试验最佳macro IoU均≤.012844，没有质量候选；这排除了“只换归一化即可恢复精度”的假设。
2. Germany197张可见性v2清单已建立，80张有post2；Top20已逐项审阅，12拒绝、3选post1、5选post2，验证有效。仍有177项待审阅，split未冻结，不能启动正式完整训练。
3. 当前配置若同时启用正类采样与正类加权会被默认拒绝；需在已冻结train/validation上分别比较，不能凭小试验选定策略。
4. Louisiana仍为已污染研究evaluation，不是最终盲holdout。正式模型指标、批准阈值、视觉/稳定性审核均缺失，production保持false。
5. GATE-5/8/9原阻塞不变：完整洪水范围与人口社区、真实资源台账、授权MapGIS完整业务终验仍缺证据。readiness为4/9。
6. preflight与验收包自动阶段已实现；当前探测MapGIS/Java/Python/CUDA可用，但AI服务和宿主未运行。最新包只提供正式GUI checklist，不能替代现场勾验。

## 2026-08-30 19:24 当前阻塞（下面旧授权/建网问题不代表当前仍失败）

1. AI诊断完成但production未通过。共享BN统计失配由同权重对照证明，GN固定样本记忆通过；历史模型单改BN无改善，仍有训练/泛化问题。GN目前只在诊断实现，未接入正式训练/API，不得直接上线。
2. 数据质量：云遮挡仍valid，只用post1；train/validation可见性策略及地物控制点配准未完整验收。少数类采样已实现，但不等于精度达标。
3. 599 Louisiana已多次研究，不是未污染holdout；正式批准指标/视觉质量与稳定性审核缺失。双层配置保持production false，不能把诊断IoU98%当独立精度。
4. GIS完整灾损仍缺完整洪水范围、可靠人口/社区、实体抽样原生核验和全链报告；SpaceNet8受淹结构标注不能填补完整洪水边界。
5. 真实/赛事认可资源台账及容量证据未补齐，已有3车仍演练；正式宿主完整业务终验和RC1未完成。现有原生拓扑/演练路径/显示证据有效，不能退回声称完全没有NetCls或授权失效。
6. 本轮实验已全部结束，无等待中的训练进程。以上多数为后续工程/数据证据工作，不是要求用户重复确认权限。当前readiness4/9，详细证据见docs/FINAL_ACCEPTANCE_REPORT.md。

## 2026-08-28 16:33 更新：不再需要用户提供联调道路/台账

用户已授权自行创建。data/demo/dispatch-spacenet8已包含20条真实官方道路、82建筑及3组明确虚构的演练车辆。道路/资源文件缺失不再是要求用户补充的阻塞。
原生建网已尝试，当前普通JVM仍DLL初始化失败，network-build.json记录false；未生成可用NetCls库。须继续修复/在已授权宿主运行新建网入口，不改许可。分钟权与资源节点绑定属于待开发，不可记作外部缺数据。


## 2026-08-28 当前验收边界

1. 当前自动化会话 IsUserAnAdmin=False。独立SDK真实栅格验收实际两次出现mapgis_geoobjects.dll/mapgis_geodatabase.dll初始化失败，切换Program工作目录后仍失败。证据runtime/native-raster-20260828a/b。不能将原因直接归为授权无效；历史官方宿主授权已通过。
2. 需要在同一已授权MapGIS官方宿主环境内执行新版原生验收与路网业务。已有“原生栅格验收”入口；未要求用户现在逐项测试。当前无桌面进程，实际target插件已更新。
3. 尚未接收到本次事件的真实MapGIS NetCls网络、分钟阻抗权、资源/需求节点、容量台账和道路核查依据。任务JSON字段见docs/DISPATCH_WORKFLOW.md；数据不可用时不生成虚构调度结果。
4. 模型非外部授权阻塞：新18组40轮已训练，精度仍很差，继续扩充有效样本/预训练与评估。无法用“推理成功”替代质量完成。

以下授权/按钮记录为历史，不代表当前仍需寻找授权文件。

## 最新验证：授权已通过，点击入口修复待重启验收

2026-08-27 20:45的logs/desktop.log明确记录云开发授权验证成功，用户截图确认项目Ribbon显示。之前的授权阻塞已经解除。

“洪涝智能识别”点击无交互根因：本机10.7.10.10的PluginJarScanner只接受com/zondy/mapgis/前缀且含plugin的入口类；旧com.mapgis.floodguard.mapgis入口被跳过，XML仍显示无命令绑定按钮。已将三个入口调整到com.zondy.mapgis.floodguard.plugin，业务实现包不变，未修改宿主二进制或授权。真实安装SDK的PluginContainer注册探针已通过，构建脚本强制运行此探针，防止仅编译通过却未注册。用户需保存工作后在管理员窗口stop_demo/start_demo重启，继续确认面板可打开。原生GIS业务及模型质量仍未验收，不是参赛成品。

## MapGIS Objects Java 21 运行授权

### 当前需要的外部操作

用户已确认：官方 `desktop-developer.bat` 管理员启动后能正常进入桌面。不能再将“许可证无效/需要重新激活”作为当前结论。此前项目启动使用非提权 java.exe，且有 Program Files 日志写入拒绝；与官方环境不一致。尚未单独隔离到底是哪项差异导致失败。

项目启动和复测现已改用官方 desktopjava.exe、GBK 控制台编码、Program 路径前置，并在启动前检查管理员权限。不修改授权文件或注册表。请在同一获授权 Windows 用户的管理员 PowerShell 中运行 `scripts/start_demo.ps1`，验证插件页面和原生 GIS。关闭该项目启动的进程时，也在管理员窗口运行 `scripts/stop_demo.ps1`。当前自动化会话没有管理员权限，因此尚未完成修正后的真实宿主复测。

脚本回归12项通过。进程存活仍不等于 GIS 验收通过；开发包尚未重新打包。以下段落保留历史结果。

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

## 2026-09-12 Germany 审查后模型质量阻塞

116 个接受样本已冻结并完成两组 40 轮 CUDA 训练。最佳宏平均 IoU 为 0.08188，但受淹道路 IoU 仍为 0；正样本采样同时使普通道路 IoU 降到 0.00128。当前阻塞是道路标签/栅格化/优化质量，不是审查进度或训练环境。两个新检查点均为 `production_ready=false`。

### 道路阻塞细化

道路监督并未消失；验证集阈值校准后普通道路/受淹道路IoU可达0.15367/0.05324。剩余阻塞是缺少独立于阈值选择的评估证据，以及受淹道路绝对精度仍低。校准检查点保持production_ready=false。
