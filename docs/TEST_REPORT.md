# 测试报告

## 2026-08-27 17:54 — 启停、跨进程模型与开发包

- 最新开发包 `release/MapGIS-FloodGuard-development-20260827-175613.zip`：129个文件SHA256全部一致、ZIP CRC检查通过；不含.lic、DLL、虚拟环境、application.local.yaml。使用开发机解释器从包目录加载模型，health返回cuda/siamunet-smoke/production_checkpoint_loaded=false。不是全新机器环境安装测试。

- run_model_e2e.ps1：Java17调用独立Uvicorn/CUDA真实烟测权重，1项通过，校验模型后端/设备/掩膜/预览/统计；停止后18767无监听。
- start_demo.ps1 -Port 18768：AI正常，MapGIS云授权失败，脚本正确报错并清理两个进程树，state.processes为空，端口无监听。该项是失败路径测试通过，不是完整Demo通过。
- 训练unittest4项通过：真实配对划分、禁止泄漏、空监督拒绝、有限梯度。
- build_release.ps1调用联合回归：AI6、脚本10、Java17核心10、fallback跨进程HTTP1、Java21 SDK10，0失败。生成开发目录与ZIP（不是参赛成品）。
- SDK新增网标时首次编译发现FlagType.nodeType与BarrierType.nodType命名不同，查本机Javadoc修正后18个源文件编译通过。

## 2026-08-27 — 官方样本、GPU 训练与可选模型后端

- download_data.ps1 -Mode sample：最初2组、后扩展6组，共19个官方对象校验通过。
- train_smoke.ps1：RTX4050 / torch2.5.1+cu121，2epochs，保存并重载 checkpoint。验证 IoU=0；只通过链路测试，不通过模型精度验收。
- `.venv\Scripts\python.exe tests\integration\verify_torch_smoke.py`：真实 checkpoint + CUDA + 官方验证影像配准后的像素夹具，经 FastAPI TestClient 提交任务，完成并生成5类掩膜/预览；production_checkpoint_loaded=false。不是实际 MapGIS E2E。
- 17:38 联合回归 run_tests.ps1：AI6、脚本5、Java17核心10、跨进程HTTP1、Java21 SDK配置10，均0失败。
- verify_mapgis_host.ps1：实际返回 authorization_failed、退出码3，准确捕获原生 GBK 授权失败。该项未通过，绝不计入成功数。
- 修复根目录直接运行 pytest 找不到 app.main：新增 ai-service/pytest.ini，重跑6项通过。

## 2026-08-27 — 资源推荐回归

- 命令：`.\scripts\run_tests.ps1`，退出码 0。
- Python 3 passed；Java 17 核心 8 passed；真实 HTTP 集成 1 passed；MapGIS Java 21 构建 8 passed并产出插件 JAR。
- 新增测试验证资源容量/类型/不可达过滤及时间排序、道路非法输入和 NaN 灾损面积拒绝。
- MapGIS 可视化、空间分析和官方模型仍未完成，以上结果不代表完整参赛 E2E。

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

## 2026-08-23 — MapGIS SDK 编译与决策业务回归

- 联合命令：`.\scripts\run_tests.ps1`
- Python：3 passed，0 failed。
- Java 17 核心：6 passed，0 failed；新增洪灾安全路径、不可达路径、HTML 报告真实数值和 HTML 转义测试。
- MapGIS Java 21：使用本机 `mapgis_pluginengine.jar`、`mapgis_geomap.jar`、`mapgis_ui_controls.jar` 编译 12 个源文件，6 tests passed，生成 `target\mapgis-floodguard-plugin.jar`。
- 产物核验：插件命令、MapGIS 结果图层加载器和 Jackson JSON 类均在 JAR 内；命令字节码 major version 65，与本机 MapGIS Java 21 SDK 一致。
- 边界：SDK 编译和打包已真实完成；仍需在 MapGIS Ribbon 宿主中完成可见加载后，才能勾选“洪涝插件加载”和“AI 结果加载至 MapGIS”。

## 2026-08-23 — 跨进程推理 E2E

- 命令：`.\scripts\run_e2e.ps1`
- 流程：生成中文路径灾前/灾后演示影像 → 隐藏启动 Uvicorn → 轮询 health → Java 提交异步推理 → 轮询 job → 校验结果掩膜存在和洪水像素统计非零 → 关闭服务。
- 结果：`RealAiServiceIT` 1 passed，0 failed；总用时约 8 秒。
- 输出：`data\outputs\e2e` 下产生实际输入驱动的 mask、preview、分类 mask 和统计文件。
- 边界：MapGIS 宿主内图层加载仍被 Objects Java 授权阻塞，因此这条测试没有伪称完整 MapGIS E2E。
