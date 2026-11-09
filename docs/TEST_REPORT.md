# 测试报告

## 2026-09-26 SpaceNet-5 外部权重迁移回归

- 权重：官方对象大小 301,620,821 字节；原始 SHA256 `716c4fa33ce211517d0699b01537f49889c35bb5e15e692a84d8452ee6daa783`；转换 state_dict SHA256 `f3201bb889bd8939d70a87c52ed4b5fb7a737bc8a83ea525416b89c37134b269`。
- 兼容性：402/402 张量严格加载；512×512 CUDA 输出 `1×8×512×512`、有限值、峰值分配 522,174,464 bytes。
- 训练可执行性：六通道 head-only 512 反向梯度有限，训练参数 1,734；10 epoch 完成，最佳 checkpoint 独立重载 IoU 一致。
- Python 语法检查通过；新增 XD_XD adapter 测试通过。
- `.\scripts\run_tests.ps1` 退出0：AI 9、项目脚本48、训练91、Java17核心54、真实HTTP1、Java21 SDK56、插件注册探针和插件构建全部通过。
- 模型判定：head-only candidate mean object IoU 0.070547 < E3c 0.290088，`promotion=rejected`；无独立 test、无 Louisiana-West 复用、`production_ready=false`。

## 2026-09-26 因子化对象/状态专项验证

- `train_full.py` 增加 factorized object/status 解码与损失；专项 `test_training` 23/23 通过，其中新增三项验证双对象状态互斥、四 logit 有限梯度、道路缓冲交叠受淹优先及单图缺少一种对象类型。
- `x=13..15` 两组 CUDA 训练均完成 14/14 epoch；history 核验前 13 轮 validation 均为 null。
- 两个 checkpoint 均由独立进程重载，在相同 105 张空间折复算；checkpoint SHA、tile count、epoch 和 prior validation reads 由 finalizer 验证。
- 封存评价判定 `promotion=rejected`；该项是开发空间对照，不是独立 test 或生产精度。
- 完整 `scripts/run_tests.ps1` 退出 0：AI 9、repository scripts 48、training 90、Java 17 core 54、真实 HTTP integration 1、Java 21 installed-SDK 56；插件注册探针与 JAR 构建通过。

## 2026-09-26 Louisiana-West 盲推理专项验证

- 新脚本 `py_compile` 通过；外部协议专项 unittest 6/6 通过，新增无标签冻结边界和 manifest 篡改拒绝。
- 冻结清单复核归档、来源许可、参考配置、E4 checkpoint 和 406 对影像哈希后，CUDA 推理完成 406/406。
- 输出报告 SHA-256：`7112debbc87c31e5c1af7e2293a4f2786b8be94f851054ab35237112db5f6881`；12 张固定可视化均生成，其中 6 张完成诊断查看。
- 此验证只证明冻结、配准、推理和报告链正常；无标签，不是准确率测试。
- 完整 `scripts/run_tests.ps1` 退出 0：AI service 9、repository scripts 48、training 87、Java 17 core 54、真实 HTTP integration 1、Java 21 installed-SDK 56；插件注册探针与 JAR 构建通过。

## 2026-09-26 外部 test 协议回归

- AI service pytest：9 passed。
- repository script pytest：48 passed。
- training unittest：87 passed，其中外部 test 协议 6 项覆盖带标签正常冻结、空间重叠拒绝、缺类拒绝、篡改拒绝，以及无标签冻结和无标签 manifest 篡改拒绝。
- Java 17 core：54 passed；真实 AI HTTP integration：1 passed；Java 21 installed-SDK：56 passed。
- MapGIS 插件注册探针通过并成功构建 `mapgis-floodguard-plugin.jar`；本轮仍未执行 GUI 业务验收。

## 2026-09-12 — Germany visibility review 工具

`.venv-training` Python3.10运行 `python -m unittest tools.visibility_review.test_review -v`：23项通过。覆盖中文路径manifest、真实旧20项只读兼容、post2缺失、未知sample、accepted无post、拒绝无理由、post2不可用却选择、日志追加/重载、原子快照失败后WAL恢复、损坏日志保留、快照非法引用报告、并发revision、统计/筛选/完成判断、备份上限、三图slot亮度与尺寸、overlay、单图损坏隔离及HTTP本地/写入令牌边界。

真实数据检查：197个唯一sample、474个manifest影像SHA256全部一致，映射/文件/review/schema异常0。全量197样本display preview与overlay缓存生成，错误0。

浏览器sandbox真实影像冒烟：PRE/POST1/POST2显示；透明Building/Road/Flood overlays显示；1、2、R、U、P、N、O有效；无理由Reject被拒绝且不跳转；textarea中的快捷键字符不触发决定；决定即时持久化并跳到下一pending；服务停止/重启后4条sandbox操作仍在；POST2缺失显示`POST2 unavailable`且按钮禁用。sandbox不写正式review；正式状态保持20/197。

## 2026-09-12 — GN正式管线小试验

`scripts/run_tests.ps1`退出0：AI服务9、项目脚本33、训练13、Java17核心53、Java→AI HTTP1、Java21 SDK55及注册探针通过；日志`logs/regression-20260912.log`。新增测试覆盖GN无BatchNorm状态、非法post选择拒绝及GN checkpoint身份重载。

真实CUDA API使用`application.gn-pilot-20260912.yaml`加载GN checkpoint并完成推理，identity字段、SHA、阈值、split hash一致；`inference_verified=true`、`accuracy_verified=false`。三组12epoch pilot均完成且指标失败，不计生产验收。readiness脚本输出`runtime/competition-readiness-20260912.json`为4/9。

## 2026-08-30 19:24 — 诊断冲刺最终回归

`scripts/run_tests.ps1`退出0，完整transcript：`logs/diagnostic-final-regression.log`。AI pytest8、项目pytest33、训练unittest11、Java17核心53、Java→AI HTTP1、Java21SDK55，全部0失败；安装SDK注册探针通过且明确GUI not tested。训练测试已纳入联合入口。数字来自本次真实输出，不作为未来固定数量断言。

本轮新增实际实验：BN/GN 2/4/8固定patch、同checkpoint归一化干预、历史模型德国抽样反证、空间/缓存40组、类别796组、分辨率8组、采样3个模拟epoch。GN每类记忆IoU≥.90只属于诊断，不是生产精度。重载同cuDNN概率误差0；TF32不同batch严格检查失败记录保留，关闭TF32后的FP32批量误差≤1.41e-6。

没有新增MapGIS GUI完整业务验收；readiness仍4/9。完整限制见AI_PIPELINE_DIAGNOSIS.md、FINAL_ACCEPTANCE_REPORT.md。

## 2026-08-28 — 道路联动、调度、报告与候选模型

- `scripts/run_tests.ps1 -E2EPort 18765`：完整退出0；Java17核心38、Java21 SDK配置38、脚本13、AI当时6、真实HTTP1、安装SDK插件注册通过。后新增模型身份测试后AI共8项通过。
- 首次run_tests失败：8765被现有服务占用，未关闭该服务。已新增独立E2EPort参数，默认18765，复测成功。
- `python -m unittest discover -s app/training -p test_training.py -v`：8项通过；包括3米道路缓冲面积、平衡损失梯度、标签与划分校验。
- `scripts/verify_native_raster.ps1`：实际两次失败，均DLL初始化失败；不是原生业务通过。a/b证据保留于runtime，第二次采用Program工作目录仍失败。宿主内新按钮尚未操作。
- `download_data.py --mode sample --count 18`：55个官方对象下载/校验完成；SHA256见data/spacenet8/sample-manifest.json。
- `train_full.py --config config/training.balanced18-stratified.json`：CUDA40轮实际完成，10/4/4划分，best验证loss0.17344268。
- `compare_research_models.py`：同4张留出影像256评价网格旧/新IoU：未淹建筑0/0.09554，受淹建筑0.02610/0.12015，未淹道路0/0.03867，受淹道路0/0.04901。样本小且同一地区，不能认为精度达标。见models/checkpoints/balanced18-comparison.json。
- `verify_research_model.py --config config/application.balanced18.yaml ...`：真实CUDA模型API任务68954cd6157b48a09a7acf389c1bb943完成，5份二值掩膜512x512、版本与checkpoint SHA256一致。见data/outputs/balanced18-api-20260828/verification.json。未修改在线8765服务。
- 原生道路映射/阻断路由/调度窗口、完整灾情统计和最终专题报告仍未现场验收，不能将单元测试数当作全部完成。

## 2026-08-27 20:15 — 模型记录导出

- run_tests.ps1：AI6、脚本10、Java17核心14、fallback跨进程1、Java21 SDK14，0失败。
- run_model_e2e.ps1：真实CUDA跨进程1项通过，生成data/outputs/model-http/58804b99497a4d049d483f75596afa34/识别记录.html（17137字节），含真实PNG内嵌预览。
- 报告测试覆盖HTML转义、缺失/超范围像素计数、拒绝伪装PNG的HTML；风险测试覆盖NaN、无穷、负权重、缺失指标。
- verify_mapgis_host.ps1：authorization_failed/code3，未通过；没有把GIS原生联调标成功。

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

## 2026-09-12 — Germany 审查冻结与训练验证

- 审查汇总：197/197 完成；接受116、拒绝81、待复核0。
- 源数据完整性：474 SHA-256 校验，0异常。
- 冻结划分：train98、validation18、test0；冻结证据与逐样本post哈希校验通过。
- 单元测试：visibility review 23 passed；training/freeze 17 passed（含证据篡改拒绝）。
- CUDA训练：两组各40/40轮完成，均生成best/last checkpoint、history与training report。
- 边界：仅Germany验证集选模；两组均`production_ready=false`，未部署。

## 2026-09-12 — 道路诊断与阈值工具验证

- 冻结Germany train/validation道路像素和正样本覆盖统计完成，未访问test/Louisiana。
- `test_training` 14项通过，新增逐类阈值选择回归。
- 校准checkpoint绑定源权重SHA-256与校准报告SHA-256，序列化后复读通过。
- 校准验证macro IoU 0.13387；这是同集拟合结果，production_ready=false。

- 两折折外阈值校准完整运行，18张验证图各自只由另一折选阈值；macro IoU 0.11405。
- AI后端真实CUDA加载校准checkpoint成功，核对GroupNorm、四阈值、数据划分哈希及checkpoint SHA-256。
- 最终复跑：visibility review 23 passed；training/freeze/calibration 18 passed。
