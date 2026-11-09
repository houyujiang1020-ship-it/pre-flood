# 开发日志

# 2026-09-26 — SpaceNet-5 XD_XD 权重接入与 head-only 迁移闭合

从 SpaceNet 官方公开 S3 下载 XD_XD SpaceNet-5 SE-ResNeXt-50 fold0，完成字节数、SHA-256 回执和旧整模型到纯 state_dict 的兼容转换；当前 PyTorch 2.5/CUDA 严格加载全部402张量，512前向通过。作者转换镜像当前403，未作为依赖。

固定0.5零样本道路对象IoU为0.012310。随后预注册并完成697/18/0、10 epoch、冻结75.3M主干/解码器与BN统计、仅训练1,734参数六通道head的开发实验。最佳第9轮 building/road/mean IoU=0.012889/0.128205/0.070547，独立重载一致；较E3c mean 0.290088低0.219541，故停止该路线、未接入四类模型。Louisiana-West/test未使用，production_ready=false。

新增可复现下载、转换、探针、预注册、封存脚本和XD_XD适配器。联合回归通过：AI9、脚本48、训练91、Java17核心54、HTTP1、Java21 SDK56及插件注册/构建。

## 2026-09-26 因子化对象/状态空间实验

- 实现 building/road object 与 object-conditional flood status 分解；四类概率由乘积解码，严格消除 0.5 阈值状态重叠。新增三项损失、梯度、缺类和互斥测试。
- `x=16..18` 预检发现道路缓冲交叉真值；候选首步失败、无 checkpoint、无候选留出评价。基线结果揭示后未继续使用该折，写入作废证据。
- 在训练前冻结新的 `x=13..15` 592/105 空间折，两个模型均随机初始化、14 epoch、final-only；前 13 轮验证读取为 0。
- 独立重载结果：基线 macro IoU 0.051853，因子化 0.000783。候选状态重叠为 0，但四类全部退化、受淹两类输出为 0，按预注册规则拒绝。
- 未读取 Louisiana-West、未部署、production_ready 保持 false。报告见 `docs/FACTORIZED_STATUS_SPATIAL_FOLD_20260926.md`。
- 完整回归通过：AI 9、scripts 48、training 90、Java core 54、HTTP 1、Java 21 SDK 56，插件注册探针与构建通过。

## 2026-09-26 Louisiana-West 无标签盲推理

- 发现并核验官方 Louisiana-West public test 归档，解压 406 条完整 pre/post1 配对；无 GeoJSON 真值。保存来源页与 CC BY-SA 4.0 许可证证据。
- 新增无标签冻结器和一次性推理器，锁定全部影像/归档/配置/checkpoint 哈希、固定 512/0.5，并确认与现有 715 张开发影像无哈希重复或正面积空间相交。
- E4 完成 406/406 CUDA 推理。四类预测覆盖率约 0.92%–1.47%，均未整体塌缩；但 flooded road 与 non-flooded road 重叠 100%，flooded building 与 non-flooded building 重叠约 99.56%。
- 六张固定抽样完成诊断检查。因无真值，IoU/F1/precision/recall 均为空，accuracy_verified/production_ready 均为 false；禁止用该 test 调参或训练。
- 外部协议专项测试由 4 项增至 6 项，增加无标签冻结和篡改拒绝。
- 完整回归通过：AI 9、scripts 48、training 87、Java core 54、HTTP 1、Java 21 SDK 56，插件注册探针与构建通过。

## 2026-09-26 外部独立 test 协议

- 实现推理前冻结器与一次性双 checkpoint 评估器，锁定来源/许可本地证据、事件区域、配对、文件哈希、四类支持、空间去重、checkpoint 和固定 0.5 阈值。
- 真实参考目录审计覆盖 Germany 116 + Louisiana 599 共 715 张，715 个灾前 SHA-256 均唯一；目录 seal 为 `c737559320a6e2481ea8377f8e5f509749a06e3bd61c23546b5e632d1bbccbf5`。
- 四项协议测试通过。当前没有外部带标签影像 test，未加载模型、未生成独立 IoU，production_ready 保持 false。

## 2026-09-26 空间外推校正与建筑状态损失

- 完成 92 张 Louisiana-East 东部空间留出的 fold-safe 校正：基础模型从随机权重训练且与留出交集为 0；下游 macro 0.088266→0.138277，但受淹建筑退化 0.013858，按预注册门禁拒绝。
- 新建 106 张 Louisiana 中部空间折，固定 14 epoch/final-only 对比独立二元与互斥建筑状态损失。候选受淹建筑 IoU 从 0.151166 降为 0，macro 从 0.076732 降为 0.045533，拒绝。
- 两组均独立重载复算一致并封存 checkpoint 哈希；未读取外部 test，未替换线上模型，production_ready 保持 false。

## 2026-09-12 Gate 5 Closure Phase 2

- 从固定数据计算 AOI bbox/centroid，并以 BKG VG250-EW WFS 空间查询确认 Dernau Gemeinde（AGS 07131017）。
- 固定 BKG 2024 Gemeinde 边界与官方人口交叉核对；下载并校验 Destatis Zensus 2022 100m 人口格网，提取 15 个 AOI 相交有值格网。
- 配置化建筑面积加权人口方法；参考估算 AOI 人口125.182、受影响人口115.077，明确等待 MapGIS 正式复算。
- 新增11项 Phase2 Python测试和1项 Java模式测试；完整回归为 AI 9、scripts 48、training 67、Java core 54、HTTP 1、Java21 SDK 56，注册probe通过。
- GUI 增加 GT VALIDATION/AI PREDICTION 明确模式。当前无 native app binding，七张真实截图未产生；风险完整输入仍缺。validator退出2，readiness保持4/9。

## 2026-09-12 13:37 — Germany visibility review 工具完成

新增独立 `tools/visibility_review` 本地Web审查器及start/stop/summarize脚本。读取现有v2 manifest和旧top20审查，不覆盖旧证据；新操作采用append-only WAL、fsync、原子快照、有限派生备份和revision冲突保护。恢复顺序为pending→needs_review→complete，实时summary只有pending/needs_review均为0才complete。

全量197样本预览已生成，统一RGB 0..255显示策略、保持宽高比，不做逐图增强。GeoJSON按每张影像自己的CRS/transform分别投影，生成透明building/road/flooded overlays；缓存元数据关联源路径、SHA、size/mtime、label SHA和策略版本。真实检查197项、474影像hash、0异常；缓存错误0。

23项自动测试通过。独立sandbox浏览器用真实样本验证三图、大图/overlay、1/2/R/U/P/N/O、拒绝理由门禁、备注输入保护、筛选/搜索、POST2 unavailable及停服重启恢复。sandbox产生4次测试决定，正式库仍为旧20项：accepted8、rejected12、pending177。生成的正式报告明确INCOMPLETE；training_split_frozen=false，未训练。

## 2026-09-12 12:48 — GN全流程与可见性准备

将GroupNorm接入共享模型工厂，训练checkpoint补全身份/阈值/split/git/metrics元数据，AI服务按同一结构重载并按checkpoint阈值推理。实际GN CUDA API任务完成，模型SHA与返回身份一致。Germany10/4完成三组12epoch、不读取test/Louisiana的对照；最佳macro分别.012844/.004641/.004912，全部失败关闭。由此新增采样+正类加权默认互斥门禁。

Germany153+44生成197项可见性v2清单，80项含post2，pre/post并排且所有源影像记录SHA。自动分数只排序；Top20逐项审阅为12 reject/3 post1/5 post2，验证器确认20项引用/候选/证据有效、177 pending、split未冻结。训练split新增官方post列显式选择与缺失拒绝。最终回归AI9、脚本33、训练13、Java53、HTTP1、SDK55通过；readiness4/9，无运行训练或模型晋级。

新增preflight与competition_acceptance入口并实际运行。preflight确认MapGIS、JDK17/21、Python双环境、CUDA和数据审计存在，同时准确记录AI/宿主未运行、production模型与真实台账缺失。最新验收包`acceptance-20260912-125202`含environment/model/data/damage/road/resource/route/report/test/evidence及GUI checklist，所有缺证据环节保持blocked/partial。

---

最新记录为本文件末尾“2026-08-30 19:24 — AI Pipeline Diagnostic Sprint”：诊断里程碑完成，4/9不变。当前交接以NEXT_TASK.md顶部及AI_PIPELINE_DIAGNOSIS.md为准，以下早期记录保留历史语境。

## 2026-08-27 20:15 — 真实识别记录与风险校验

- HtmlInferenceReport从真实任务返回生成HTML，内嵌PNG、实际像素统计、输入路径和原始证据；明确不是完整GIS灾情报告。新增桌面导出按钮，拒绝覆盖已有文件、非PNG预览、不一致像素数，并转义文本。
- 修复RiskCalculator允许NaN、负权重和缺失指标默认为零的问题；未知指标现在拒绝评分，不再当作低风险。
- run_tests：AI6/脚本10/Java17核心14/HTTP1/Java21 SDK14全通过；run_model_e2e另行通过，真实CUDA结果生成识别记录。官方授权复测仍返回code3。

## 2026-08-27 — 插件入口、生命周期和开发包

- 从已安装宿主application.xml生成项目独立XML，增加真实IRibbonPage/IRibbonPageGroup和ICommand。通过官方--custom-ui选项使用，不修改安装目录。空间化按钮调用原生适配器，仍待授权现场核验。
- 新增demo_manager/start_demo/stop_demo，记录PID+创建时间+命令行，停止前校验身份，只结束本次进程树；端口占用时拒绝干扰其他服务。授权失败后实际清理成功。
- Java跨进程调用真实GPU模型通过，不再允许“只测health”冒充推理集成；零预测也允许合法返回，不靠非零像素伪造精度。
- 开发包复制开源架构/许可、样本/来源、最小权重、代码和文档，不包含专有SDK、许可证、个人配置或虚拟环境，生成SHA256清单。所有未完成项明确保留。

## 2026-08-27 — 真实数据、GPU 和桌面面板

- 官方 S3 下载配对与标注，灾前1300×1300/灾后约786×786，隔离科研环境按地理参考配准，不以拉伸代替配准。
- pip 的 download-r2 PyTorch 入口极慢，改用同一官方 download.pytorch.org CloudFront 文件；SHA256 与官方索引9b22d6d98aa56f9317902dec0e066814a6edba1aada90110ceea2bb0678df22f一致。
- RTX4050实际完成烟测，checkpoint保存重载成功，IoU0如实保留。最终推理环境增加纯PyTorch后端，不带Rasterio。
- 插件新增影像选择、输出选择、非阻塞任务进度、取消等待、预览及错误信息。未经空间参考验证的PNG不自动加载地图。编译通过，UI运行仍待授权。
- 原授权检测错误地强制 .lic；修为云开发参数并保留官方校验。原生日志混合GBK/UTF8导致失败识别漏报，改为Python保留原始字节，双编码匹配，实测准确返回失败。
- 本机找到 MapGIS_Java_Api 10.7.10.10 完整Javadoc，后续空间化/网络分析优先依据该文档和JAR编译验证。

## 2026-08-27 — 资源推荐与输入健壮性

- 新增 ResourceDispatcher：按资源类型、容量和可达性过滤，再按预计时间排序；路线提供器可替换，当前不冒充 MapGIS 网络分析。
- 修复道路输入允许负距离、零速度、NaN 和无效标识的问题；灾损面积拒绝非有限数值。
- E2E 增加生成失败、端口占用和子进程提前退出检查，避免误测其他服务。
- 实测总回归退出码 0：Python 3，Java 17 核心 8，HTTP 集成 1，Java 21 SDK 构建测试 8，全部通过。

## 2026-08-23 — 工程初始化

- 问题：尚无工程骨架和环境事实。
- 处理：建立固定目录结构，开始环境审计与 MapGIS SDK 探测。
- 验证：目录和状态文件实际存在。

## 2026-08-23 — MapGIS 与上游探测

- 问题：最初常见路径探测未包含带版本号的安装目录；SpaceNet8 partial clone 无数据增长。
- 原因：本机安装目录为 `C:\Program Files\MapGIS 10`；Git partial-clone 对象获取路径网络异常。
- 解决：从运行服务的可执行路径反查安装根目录；SpaceNet8 改为浅克隆。
- 涉及：`docs/ENVIRONMENT_REPORT.md`、`docs/UPSTREAM_LOCK.md`。
- 验证：MapGIS 三项服务运行，Objects Java JAR 和三个自带 JRE 实际存在；MapGIS 上游 commit 已读取。

## 2026-08-23 — 开发工具链恢复

- 问题：Temurin JDK 8 的 GitHub MSI 下载停滞；系统缺少 Maven；默认 Maven 控制台误显示中文路径。
- 原因：GitHub 大文件通道速度异常；Maven 未提供适用的 winget 包；Java 默认采用 GBK。
- 解决：安装 Python 3.10 并创建 `.venv`；使用 Microsoft 官方 ZIP 部署 JDK 17；下载 Apache Maven 3.9.16 并校验 SHA-512；设置 `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8`。
- 涉及：`scripts/setup_python.ps1`、`scripts/setup_java.ps1`。
- 验证：Python 3.10.11、Java/Javac 17.0.20.1、Maven 3.9.16 均在中文项目路径实际运行成功。

## 2026-08-23 — SpaceNet8 工作树与 MapGIS 构建试验

- 问题：SpaceNet8 partial clone 已取得 commit/tree，但 blob 未完整下载，检出失败；MapGIS 旧上游首次 Maven 构建缺少 JavaFX 类。
- 原因：GitHub blob 通道异常；Microsoft JDK 17 不捆绑 JavaFX，而 2020 年上游源码依赖 JavaFX 及 `com.sun.javafx` 内部包。
- 解决：下载并展开 GitHub 官方 codeload `main` 归档，使用 partial clone 与 GitHub API 共同锁定 commit `30ca30c...`；JavaFX 构建问题保留为下一项真实兼容工作，不伪造构建成功。
- 验证：SpaceNet8 根 README、LICENSE、baseline README 均存在；MapGIS Maven 已成功进入源码编译阶段，失败点明确为 JavaFX 类路径而非 JDK/Maven不可用。

## 2026-08-23 — AI Service MVP

- 问题：官方 SpaceNet8 仓库未提供可直接使用的 baseline `best_model.pth`；历史运行环境携带重型 GIS 依赖。
- 原因：README 只给出用户训练后 checkpoint 的路径；baseline 将科研预处理、模型和 GIS 后处理放在同一 Docker 环境。
- 解决：建立独立 FastAPI/CLI 架构和明确标识的变化分析 fallback；不引入 GDAL/Fiona/GeoPandas；API 明示生产 checkpoint 未加载。
- 涉及：`app/ai-service`、`scripts/start_ai.ps1`、`scripts/run_tests.ps1`、`docs/API.md`。
- 验证：pytest 3 passed；Uvicorn 实际启动且 `/health` HTTP 200；中文路径推理结果文件存在且统计非零。

## 2026-08-23 — Java AI 客户端与风险引擎

- 问题：桌面端尚无可测试的 AI 服务调用边界，也缺少独立于 UI 的风险计算核心。
- 解决：新增 Java 17 Maven 模块、异步任务 DTO、HTTP 客户端、结构化异常和可配置风险评分器；测试使用本地 HTTP mock，并增加真实 Python 服务集成测试。
- 调试记录：首次从 PowerShell 传递 `-Dai.url=...` 时未加引号，被 Maven 解析成错误生命周期参数；改用单引号包裹完整 `-D` 参数后通过。
- 验证：Java 单元测试 3 passed；真实 Java→Uvicorn `/health` 集成测试 1 passed，Python 服务日志确认 HTTP 200。

## 2026-08-23 — MapGIS Java 21 插件适配

- 问题：JDK 17 编译本机 MapGIS JAR 时报告类文件版本 65 与编译器版本 61 不兼容。
- 原因：当前安装版 MapGIS 10 SDK 已使用 Java 21 构建，而独立业务核心仍以 Java 17 为最低运行版本。
- 解决：安装 Microsoft OpenJDK 21.0.12.1；采用双构建模式，核心测试继续使用项目 JDK 17，`mapgis-sdk` Profile 使用 JDK 21 和真实本机 SDK JAR；增加阴影插件包但排除宿主提供的 MapGIS/JavaFX。
- 涉及：`app/mapgis-flood-desktop/pom.xml`、`src/mapgis/java`、`scripts/build_mapgis_plugin.ps1`。
- 验证：MapGIS Profile BUILD SUCCESS，6 tests passed，插件 JAR 字节码版本 65。

## 2026-08-23 — 应急决策核心

- 实现：道路积水分级、不可通行边剔除、积水阻抗惩罚的 Dijkstra 安全路径；灾损汇总 DTO；基于真实输入值的 UTF-8 HTML 灾情报告。
- 验证：安全路线主动绕过阻断捷径；不可达场景抛出结构化错误；报告中文、数值和 HTML 转义测试通过。

## 2026-08-23 — MapGIS Java 宿主启动试验

- 命令：使用安装目录 JRE 21、Program 和 `lib` 全类路径启动官方 `DesktopLauncher`。
- 结果：官方启动器、JavaFX 21 和 UI 字体成功初始化，随后在产品授权阶段报告目标 `.lic` 缺失，并且硬 Key 验证失败。
- 处理：未把“洪涝插件加载”或“AI 结果加载至 MapGIS”标成完成；授权细节已写入 `BLOCKERS.md`，增加补齐许可后的宿主验证脚本。

## 2026-08-23 — 自动化跨进程 E2E

- 实现：可重复生成中文文件名演示影像；PowerShell 隐藏启动/健康等待/可靠关闭 AI 服务；Java 从真实 HTTP 服务提交任务并校验输出文件和统计结果。
- 验证：`.\scripts\run_e2e.ps1` BUILD SUCCESS，1 integration test passed；没有遗留 Uvicorn 进程。
# 2026-08-28 道路调度增量与训练改进

新增RoadClosurePlan/DispatchRequest、原生getSubEdgeS源实体映射、DispatchPanel及可追溯HTML/JSON报告包，接入ExposurePanel。阻断需核查证据；不会把相交自动等同封路。原生路径检查节点/端点/阻断边，拒绝经纬度网络直接算公里。目标/类型/需求变化会废弃旧方案。

实际独立SDK栅格探针两次DLL初始化失败，已保留失败证据；没有改授权。新宿主内验收按钮尚未测试。当前无桌面进程，target插件已更新；Java38/AI8/脚本13/HTTP1/训练8及SDK注册通过。run_tests首轮因8765占用失败，改独立18765后整体成功。

科研环境安装Shapely2.1.2/pyproj3.7.1（3.7.2不支持Python3.10，安装失败后选兼容版本），最终AI环境核验均无Shapely/pyproj/Rasterio。预处理补官方3mUTM道路缓冲与有效像素掩膜。18组官方数据下载完成；初始验证缺受淹建筑，在拟合前调整train/val、测试不变。256px平衡BCE+Dice训练40轮，4类IoU仍很低（详见比较报告），没有上线替换。/model/info曾错误返回fallback版本，现与推理一起返回已加载权重SHA256身份。新候选CUDA真实API检查通过。
# 2026-08-28 16:33 自行生成道路与资源演练数据

用户要求不再索要数据，已生成真实SpaceNet8 0_41_59道路20/建筑82，虚构车辆3组，明确演练标记。普通JSON提取保留原几何，无Python GIS建网。配套研究影像pre/post512px已生成。prepare_dispatch_data新增2项测试通过（脚本总15）。MapGIS原生建网代码和GUI入口编译通过、Java38、SDK注册通过，target更新；实际独立JVM尝试失败于DLL初始化，失败证据保留，不当作创建成功。下一步宿主运行/分钟权/节点绑定/跨CRS核查联动。
# 用户宿主建网失败：数据库名超长

实际宿主已连接MapGISLocal，createGDB失败。旧数据库名FG_Exercise_加32字符UUID共44ASCII字节，违反官方CreateGDBDialog.validateDBName的32字节限制。修正27字节名称，添加长度/格式/确定性测试；同时对齐官方GDBCreateParam本地HDF文件初始化和增长参数，并增加阶段/名称/文件证据。独立db-create-fix-build构建及Java40、SDK注册通过；尚未在宿主复测，不将编译等同创建成功。
# 道路线类创建返回0：修正错误重载

宿主证据74b9c4d4确认数据库已建成且URL有效。SFeatureCls两参数create接收完整URL，误传普通类名导致失败。按安装SDK Javadoc及官方CreateDataDialog改五参数create(name,GeomLin,0,geographicId,null)。同时增加导入数量、类打开状态、道路ID和阶段日志。road-create-fix-build编译及Java40、SDK注册通过；原生运行尚待部署，不以编译冒充业务通过。
# 2026-08-30 19:24 — AI Pipeline Diagnostic Sprint

遵照先诊断不盲训：读取现状及未提交工程，基线联合回归退出0；固定4类均有正类的8个训练crop，分别运行2/4/8无增强、无Dropout记忆对照。原BN eval每类未达.90，同checkpoint仅改encoder统计使macro从.672/.587/.899升为.969/.998/.9997；GN替换诊断在150/150/200步达到macro .9817/.9593/.9777。没有更新线上权重。

另用历史tempered模型德国train/val各8张反证：单改BN并未改善，不能宣称归一化是历史低精度唯一原因。GN重载需匹配cuDNN设置，TF32跨batch最大.00260误差；保存失败证据后用FP32验证批量不变性≤1.41e-6，原概率重载一致。

并行完成40组空间重算缓存精确一致、796类别分布、6张目视审阅、8组分辨率对照。发现nodata-valid未屏蔽云；trainFB/FR仅35/49个tile，纯背景tile0；8组38道路无512完全消失。添加正类采样可选路径（含缺类/跨split拒绝、配额/覆盖报告），保持旧缓存和checkpoint签名保护。

添加config/model_acceptance.yaml双层失败关闭策略及离线验证，readiness schema v2仍4/9。最终联合回归AI8/脚本33/训练11/Java53/HTTP1/SDK55+注册全部通过。报告、状态交接及参赛文档生成源已更新；旧DOCX未再生成，不作为正式RC。无第三轮正式训练、无新GUI业务pass、无真实台账或人口伪造。

---

## 2026-09-12 — Germany visibility review 工具启动检查

已读取 PROJECT_STATUS、NEXT_TASK、BLOCKERS、DEVLOG、AI_PIPELINE_PILOT_20260912、TEST_REPORT 和 prepare/validate_visibility_review.py。真实 v2 目录只有 visibility_manifest.json、top20_visual_review.json、review_status.json、review_queue_top20.png，尚无逐样本缓存。manifest 197 项，train153/validation44，80 项有 post2；原审查20项（accepted8：post1=3/post2=5，rejected12），pending177。旧审查采用 split+label 键和 post-event image 1/2/reject；将只读兼容，不重写原文件。影像路径来自 manifest，标签在同 area 的 annotations 下并核对真实映射表。已有预览将 RGB 裁到0..255，不做逐图强对比拉伸；新缓存沿用范围并保持宽高比。使用独立 tools/visibility_review，复用 .venv-training Python3.10，补与现有AI环境同版本 FastAPI/Uvicorn（不改AI服务）。已有大量未提交项目修改，保留。training_split_frozen=false，不训练。

## 2026-09-12 — 审查完成、冻结数据并执行两组训练

用户完成 197/197 审查：接受116、拒绝81、待复核0，post1=91、post2=25。全量474个源文件哈希无异常，审查服务已停止。冻结数据集保留原split边界（train98/validation18/test0），划分哈希为 `14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1`；训练入口增加审查状态、日志、manifest和所选post逐文件防篡改校验。

依次完成 GroupNorm+类别加权损失与 GroupNorm+正样本感知采样两组40轮CUDA训练。最佳验证macro IoU为0.07780与0.08188。采样组受淹建筑IoU升至0.10007，但普通道路IoU仅0.00128，受淹道路仍为0。两者均保留production_ready=false，未访问Louisiana/test选模，未部署。

## 2026-09-12 — 道路概率诊断与研究阈值校准

新增冻结缓存道路分布和checkpoint概率诊断。train道路覆盖92/28张（普通/受淹），validation覆盖16/3张，确认3m缓冲标签在512栅格中存在。修复calibrate_thresholds对GroupNorm和空test split的兼容，加入冻结证据校验和0.01步长阈值候选。采样模型验证阈值确定为0.54/0.45/0.18/0.25，四类IoU为0.22707/0.10149/0.15367/0.05324，macro 0.13387。生成研究副本，production_ready=false，未部署；同一validation选阈值和报告，不能当独立精度。

补充两折折外阈值评价，每张图只用另一折选择阈值：四类IoU 0.22342/0.05494/0.15317/0.02468，macro 0.11405。道路两类均不再为0，但两折受淹道路阈值为0.12/0.38，显示仅3张正类验证图带来高不确定性。未据此发布或继续对同一验证集调参。

## 2026-09-12 道路诊断与 Experiment C 已完成（当前状态）

- 人工审查197/197：accepted116/rejected81/pending0；冻结train98/validation18/test0，split未变。
- 原普通道路IoU从history与checkpoint恢复为0.001282982062548399，污染已修复并扫描；正负道路概率部分可分但存在明显重叠，不能仅归为校准问题。
- germany-reviewed-v1已冻结旧sampler第37轮权重及开发阈值0.54/0.45/0.18/0.25，candidate_type=development，production_ready=false。
- C仅改sampler，用户确认继承已有Dice=0.5；40轮完成，最佳第40轮。固定0.5 macro=0.072419；原冻结阈值macro=0.107021；新同集开发校准macro=0.122391；两折OOF macro=0.103920。
- 三项重点类别在冻结阈值及OOF下均退步，C不晋级、未部署。D仅建议设计road-aware overlap loss单变量对照，本轮没有运行D、没有增加epoch。
- 完整回归通过：AI9、脚本33、训练26、Java核心53、HTTP1、SDK55与注册探针。
- 本轮没有读取Louisiana、test或future blind holdout。OOF仅把阈值选择折外化，不是独立模型精度。
- 报告：docs/ROAD_PROBABILITY_DIAGNOSIS.md、docs/EXPERIMENT_C_COMPARISON.md。实验目录：models/experiments/germany-reviewed-gn-class-aware-sampler-20260912。无运行中训练任务。


## 2026-09-12 Experiment D completed（当前状态）

- Experiment C completed，promotion=rejected，原始产物封存哈希全部保持不变。
- 真实baseline loss=BCE+0.5×四通道平均Dice；D仅替换道路Dice为Tversky（FP alpha0.4/FN beta0.6，smooth0.5），建筑loss/BCE/旧sampler/其余训练条件冻结。
- D完成40epoch，best epoch=38；0.5 macro=0.080968；原冻结阈值macro=0.127678；same-validation calibration macro=0.129752；threshold OOF macro=0.114459。均非独立模型精度。
- Experiment D promotion=rejected；production_ready=false；未修改在线模型或原candidate thresholds。
- 停止本轮模型微调；下一步仅two-stage architecture feasibility study（Stage1建筑/道路分割，Stage2受淹/非受淹分类）。本轮未启动E、未实现或训练two-stage。
- Germany split仍98/18/0，SHA256=14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1；不重做审查。blind_holdout_used=false；Louisiana_used=false；test_used=false。没有查找/预览/推理future holdout；未来需独立准备并封存，不能用作调参。
- 完整回归通过；另形态6项、排序3项通过。报告：docs/LOSS_FUNCTION_AUDIT.md、docs/EXPERIMENT_C_FINAL.md、docs/EXPERIMENT_D_COMPARISON.md。
- 训练结束，无运行中训练任务。以下较早记录为历史。

## 2026-09-12 Two-stage architecture feasibility

- 从正式四通道pipeline派生building/road union与GT-gated status标签；98/18 split审计无subset violation。
- 新增2-channel SiamUnet支持、Stage1对象sampler/loss、Oracle gate loss、自动测试、checkpoint、阈值/AP/形态评价与single-stage union公平对照。
- Stage1与Oracle Stage2各完成40epoch；Oracle 2/4/8样本sanity loss分别下降90.7%/83.7%/97.6%。
- 决策CASE A：建议未来独立开展Predicted-Gate Integration；本轮按停止条件结束。blind_holdout_used=false，Louisiana_used=false，production_ready=false。
- 完整回归退出0：AI 9、脚本33、训练53、Java核心测试、HTTP集成1、Java21 SDK 55及插件注册探针均通过。
## 2026-09-12 Predicted-Gate integration

- 重新核验Stage1/Oracle Stage2全部冻结哈希，预先锁定object/status阈值、soft语义乘积阈值与PG-A/B/C规则；未训练模型。
- Germany validation18完成Stage1/Stage2独立推理、Hard/Soft四类重构、gate recall、Oracle retention、错误分解、connected-component、道路形态及三张固定可视化。
- 判定PG-B：Hard Flooded Road IoU 0.097，较single-stage 0.053提升0.044但未达到预声明+0.05；macro IoU下降；Flooded Road GT中56.0%由Stage1 gate漏掉，仅8.2%为gate内status误判。
- 不晋级two-stage predicted-gate candidate；recommended_integration=hard仅作未来可解释集成参考。production_ready=false，blind_holdout_used=false，Louisiana_used=false。
- 完整回归通过：AI 9、脚本33、训练60、Java核心、HTTP集成1、Java21 SDK 55及插件注册探针；新增Predicted-Gate专项测试7项通过。
## 2026-09-12 Stage1 Road Gate Bottleneck Study

- 核验Predicted-Gate completion manifest全部SHA256后，对Germany validation18完成逐图、宽度、组件、概率、边缘/NoData、encoder尺度与失败案例审计。
- 确认pipeline是1300×1300整图缩放至512；道路宽度中位数13→5 px，但≤4 px仅0.82%，组件宽度与gate miss无正向关系，Flooded Road也未比普通Road更易漏。
- 高分辨率启动条件不成立，未运行Stage1-E或任何新训练。model_research_phase_paused=true；production_ready=false；blind_holdout_used=false；Louisiana_used=false。
- 完整回归通过：AI 9、脚本33、训练67、Java核心、HTTP集成1、Java21 SDK 55及插件注册探针；Road Gate Audit专项测试7项通过。
