## 2026-09-26 SpaceNet-5 迁移后的模型路径

XD_XD SpaceNet-5 官方道路权重已完成下载、转换、严格加载和本域实验。不要把其零样本输出直接用作 gate；不要在 Germany validation 或 Louisiana 已揭示空间折继续搜索解冻层数、学习率、阈值或 epoch。冻结主干只训练 1,734 参数 head 的 mean object IoU 仅 0.070547，已按预注册停止。

E4 继续是四类 research leader。下一项有效 AI 模型工作需要新的带四类真值地理区域：先冻结来源、许可、空间独立性和训练/最终留出，再做同架构随机初始化 vs SpaceNet-5 道路全量微调；建筑分支应使用建筑专用预训练或 E3c，而不是复用道路概率。Louisiana-West 仍永久禁止训练、校准和重复选模。

## 2026-09-26 因子化状态实验后的模型路径

对象×条件状态的固定 0.5 候选已在新的 `x=13..15` 空间折失败并拒绝。不要在该折调 product 规则、状态权重、阈值或追加 epoch，也不要把零状态重叠本身当作精度提升。此前 `x=16..18` 的协议前提失败已单独作废，不能引用其未完成比较。

E4 继续保留为 Germany 开发集 research leader。当前 Germany validation、Louisiana `x>=22`、`x=19..21`、`x=16..18` 和 `x=13..15` 都已用于开发诊断，不再从这些空间折启动新的结构/阈值搜索。下一有效模型门禁需要新的带四类真值地理区域；若新增带标签训练数据，应先冻结新的空间分组，再研究 foundation 对象定位与对象级状态分类，不能使用 Louisiana-West public test 训练或调参。

## 2026-09-26 Louisiana-West 之后的直接执行路径

Louisiana-West public test 已完成封存和一次性无标签推理。不要再次运行、调阈值、选模型或把它加入训练。当前结果只揭示四类均有响应以及 flooded/non-flooded 状态通道高度重叠，不能生成 IoU。

AI 的下一有效入口是新的、具有四类真值且与 715 张开发影像及 Louisiana-West 均独立的数据。按 `config/external-test-intake.example.json` 保存来源与许可证证据，先运行 `scripts/freeze_external_test.py`，再按固定 0.5 只评估一次；随后运行 `scripts/verify_model_acceptance.py`。在此之前不得声称独立精度。

## 2026-09-26 空间实验闭合后的唯一模型路径

无泄漏 foundation 空间对照已经完成但因受淹建筑退化而拒绝；互斥建筑状态损失也在新的中部空间折上失败并拒绝。不要继续复用 `x>=22` 或 `x=19..21` 调阈值、epoch、loss 或结构，也不要晋级这些检查点。

当前保留 E4 Germany 开发集 research leader。AI 下一步只接受用户尚未下载的外部独立 test：先冻结来源、许可、灾前/灾后配对、四类标签语义、与全部训练及开发折的空间重叠、文件清单和 SHA-256；有真值才按预声明固定 0.5 一次性计算 IoU，无真值只做推理展示。外部 test 到位前不再从已揭示的 Louisiana/Germany 开发集选择模型。`production_ready=false`。

工程侧剩余路径不变：在管理员、已授权 MapGIS Desktop 会话内运行 Gate 5 Phase 2，完成正式空间复算、七张 GUI 截图和业务签署；随后再根据 readiness 证据推进后续 gate。

## 2026-09-26 空间验证后的模型路径（历史）

首次 foundation 空间对照因初始化 checkpoint 已见过 92 张条带而作废，不得引用 0.15196 作为泛化指标。当前应先从随机权重训练一个完全排除该条带的 fold-safe foundation，再按同一固定 14 epoch/final-only 协议重跑四类模型。完成这一纠正前不要启动互斥状态实验，也不得在该条带调阈值、epoch 或 loss。

E4 继续保留为 Germany 开发集 research leader，不标记 production。独立 test 到位后仍按冻结来源、许可、配对、标签语义、空间重叠和 SHA-256 的流程只评估一次。

## 2026-09-26 E4 后续（当前唯一有效模型路径）

E4 foundation 初始化四类模型已晋级为 research leader：`models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth`，固定 0.5 macro IoU 0.16066。soft gate 已按单次预注册评估并拒绝；不要继续搜索 gate strength、threshold、EMA、crop/stride 或追加 epoch。

下一步必须转向独立性：用户的外部 test 数据到位后，先冻结来源、许可、配对、四类标签语义、空间重叠与 SHA-256，再按预声明固定 0.5 只评估一次。若近期仍无 test，则先建立按地理块分组的开发交叉验证，评估 E4 相对旧 leader 的稳定性；不得再以当前 18 张 Germany validation 做结构选择。任何独立性验证完成前保持 `production_ready=false`，不替换线上模型。

## 2026-09-26 E2 后续

E2 原分辨率裁块已完成并拒绝晋级；不要继续调 crop size、stride 或增加 epoch。下一步 E3 回到稳定的 512 数据口径，训练 foundation 模型，主要输出建筑 body 和道路 body，并增加建筑 border/contact、道路 skeleton/junction 辅助通道。先在训练前固定当前四通道 research leader 的建筑/道路 union 同口径基线；E3 只评价 object foundation，不修改洪涝模型。通过后才用 foundation 权重初始化 E4 Siamese flood。

## 2026-09-26 E1 后续

E1 EMA 已完成并拒绝晋级；不要搜索其他 EMA decay。当前继续 E2：以原始 1300×1300 网格生成对齐缓存，训练 448×448 正类感知裁块，validation 用重叠滑窗合成为完整尺寸后计算固定 0.5 四类 IoU。除分辨率/裁块/推理拼接外，保持域平衡 sampler、SiamUnet_diff、GroupNorm8、BCE+0.5 Dice、学习率和 30 epoch 不变。必须先测试 crop 坐标同步、边缘覆盖、融合权重和无标签泄漏。

## 2026-09-26 AI 改进下一步

域平衡训练已完成，当前开发验证 research leader 为 `models/experiments/germany-louisiana-domain-balanced-20260926/best_model.pth`，固定 0.5 macro IoU 0.14390。下一步按 `docs/OPEN_SOURCE_ALGORITHM_ADAPTATION_20260926.md` 做 E1 EMA 单变量对照；数据、split、采样、模型、loss、epoch 和阈值保持不变。随后才做 E2 原分辨率 384/448 裁块与重叠推理。不要同时更换 backbone/loss/增强，也不要使用未来 test 选轮次或调阈值。

当前 18 张 Germany validation 已被反复用于开发选择；进入 foundation 辅助监督和 soft-gated Siamese 结构前，应准备按地理块分组的开发折。test 到位后先冻结来源、许可、配对、标签语义、空间重叠和 SHA-256，只运行一次预声明评估。当前模型保持 `production_ready=false`。

## 2026-09-16 新模型的独立 test 后续

Germany + Louisiana-East 研究训练已完成；最佳 checkpoint 只作为研究候选。用户尚未下载另一个 test 数据集。收到后先核对路径、许可、配对、四类标签及与训练/验证影像的空间重叠，冻结 test 清单和 SHA-256；若无标签则只做推理展示，不生成 IoU。不得用 test 调阈值、选轮次或继续训练。具体结果见 `docs/GERMANY_LOUISIANA_EAST_RESEARCH_20260916.md`。

## 2026-09-12 Gate 5 Phase 2 后续唯一闭环路径

Community 与 population 来源已经补齐，不再下载或替换。下一步仅在真实授权 MapGIS Desktop 中按 `docs/GATE5_GUI_EVIDENCE_CHECKLIST.md`：加载固定 AOI、BKG Dernau 面、Zensus 100m 人口格网和真值实体，复算实体归属/跨界道路长度/人口估算，生成七张截图与 desktop.log；同时为正式 flood、道路可达性、医疗可达性指标提供真实可追溯依据后复用 RiskCalculator。完成前 Gate 5 保持 BLOCKED 和4/9。不要开始 Gate8，不要恢复AI研究或修改Gate6/7、production_ready。

## 2026-09-12 Gate 5 后续路径（Phase 1 历史）

Gate 5 参考分析已经完成但状态为 BLOCKED。下一步仅接受固定 `0_41_59` 范围的真实/赛事认可社区边界与人口数据，必须同时提供来源、许可、日期、CRS、范围和 SHA-256；补齐后计算社区/人口与五项风险指标，并在授权 MapGIS 宿主内完成 `GROUND_TRUTH_VALIDATION` 原生查询、GT/AI 明确区分显示、截图/日志/JSON/HTML/run_id 证据。未补齐前不得将缺失值记0或把 Gate 5 标为通过。不得转回模型训练、调阈值、读取 Louisiana/future blind holdout，也不得改变 Gate 6/7 或 production readiness。

## 2026-09-12 Experiment D completed（当前状态）

- Experiment C completed，promotion=rejected，原始产物封存哈希全部保持不变。
- 真实baseline loss=BCE+0.5×四通道平均Dice；D仅替换道路Dice为Tversky（FP alpha0.4/FN beta0.6，smooth0.5），建筑loss/BCE/旧sampler/其余训练条件冻结。
- D完成40epoch，best epoch=38；0.5 macro=0.080968；原冻结阈值macro=0.127678；same-validation calibration macro=0.129752；threshold OOF macro=0.114459。均非独立模型精度。
- Experiment D promotion=rejected；production_ready=false；未修改在线模型或原candidate thresholds。
- 停止本轮模型微调；下一步仅two-stage architecture feasibility study（Stage1建筑/道路分割，Stage2受淹/非受淹分类）。本轮未启动E、未实现或训练two-stage。
- Germany split仍98/18/0，SHA256=14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1；不重做审查。blind_holdout_used=false；Louisiana_used=false；test_used=false。没有查找/预览/推理future holdout；未来需独立准备并封存，不能用作调参。
- 完整回归通过；另形态6项、排序3项通过。报告：docs/LOSS_FUNCTION_AUDIT.md、docs/EXPERIMENT_C_FINAL.md、docs/EXPERIMENT_D_COMPARISON.md。
- 训练结束，无运行中训练任务。以下较早记录为历史。

## 2026-09-12 道路诊断与 Experiment C 已完成（当前状态）

- 人工审查197/197：accepted116/rejected81/pending0；冻结train98/validation18/test0，split未变。
- 原普通道路IoU从history与checkpoint恢复为0.001282982062548399，污染已修复并扫描；正负道路概率部分可分但存在明显重叠，不能仅归为校准问题。
- germany-reviewed-v1已冻结旧sampler第37轮权重及开发阈值0.54/0.45/0.18/0.25，candidate_type=development，production_ready=false。
- C仅改sampler，用户确认继承已有Dice=0.5；40轮完成，最佳第40轮。固定0.5 macro=0.072419；原冻结阈值macro=0.107021；新同集开发校准macro=0.122391；两折OOF macro=0.103920。
- 三项重点类别在冻结阈值及OOF下均退步，C不晋级、未部署。D仅建议设计road-aware overlap loss单变量对照，本轮没有运行D、没有增加epoch。
- 完整回归通过：AI9、脚本33、训练26、Java核心53、HTTP1、SDK55与注册探针。
- 本轮没有读取Louisiana、test或future blind holdout。OOF仅把阈值选择折外化，不是独立模型精度。
- 报告：docs/ROAD_PROBABILITY_DIAGNOSIS.md、docs/EXPERIMENT_C_COMPARISON.md。实验目录：models/experiments/germany-reviewed-gn-class-aware-sampler-20260912。无运行中训练任务。

下一步：保留旧development基线。可制定Experiment D方案，明确与已有Dice的关系及晋级标准后再实验；不要重做审查、改split或读取blind holdout。以下内容仅为历史。

# 下一步任务

## 2026-09-12 13:37 当前人工审查入口

Germany审查工具已完成并运行于启动脚本输出的本地URL。正式状态仍是20/197，剩余177项；使用 `.\scripts\start_visibility_review.ps1 -OpenBrowser` 恢复首个pending，完成后运行 `.\scripts\summarize_visibility_review.ps1`。在pending与needs_review清零前不冻结split、不启动完整训练。工具实现、数据语义和恢复说明见 `tools/visibility_review/README.md`；完整性报告在v2审查目录。

## 2026-09-12 12:48 唯一当前断点（以下均为历史）

**最后完成步骤**：GroupNorm训练→checkpoint→FastAPI重载→真实CUDA推理全链贯通；Germany 10/4三组12-epoch试验完成；Germany可见性v2清单生成，Top20逐项审阅（12 reject/3 post1/5 post2），验证器确认20/197有效、177 pending、split未冻结；联合回归退出0；readiness仍4/9。

自动交付脚本也已落地并实测：`runtime/preflight-20260912.json`；最新验收包`runtime/acceptance/acceptance-20260912-125202`。当前宿主/AI端口未运行，production模型和真实资源缺失，包内状态保持false。

**当前实验PID**：无。三个pilot均已完成。日志：`logs/gn-pilot-20260912.log`、`logs/gn-sampler-pilot-20260912.log`、`logs/gn-loss-pilot-20260912.log`、`logs/regression-20260912.log`。

**最新checkpoint**：三个研究checkpoint位于`models/experiments/siamunet-gn-*-pilot-20260912`。其中API实际验证的是`siamunet-gn-pilot-20260912/best_model.pth`，SHA256=`4e4dce78661fa1ac3b51947178d4bc1aac241325b76ee52303782edaac4207fb`；其最佳验证macro仅.012844，禁止promote。

**最后测试**：AI9、脚本33、训练13、Java17核心53、HTTP1、SDK55及插件注册通过。API验证：`data/outputs/gn-pilot-api-20260912/verification.json`，inference_verified=true、accuracy_verified=false。

**下一步**：继续`experiments/diagnostics/visibility/germany-20260912-v2`剩余177项可追溯审阅，明确reject/选择post1/post2；当前自动指标只排序，不能自动决定。审阅后生成新的Germany train/validation配置与缓存身份，预声明最多两个完整对照：GN+均匀采样+温和加权，以及GN+正类采样+普通BCE/Dice。不得同时重复再平衡；不得读取Louisiana选模型。若未完成可见性冻结，禁止启动完整40epoch。

**先读取**：`docs/AI_PIPELINE_PILOT_20260912.md`、`experiments/diagnostics/visibility/germany-20260912-v2/visibility_manifest.json`、`top20_visual_review.json`、`review_status.json`、三组training_report、`runtime/competition-readiness-20260912.json`。

**下一步命令**：

```powershell
Set-Location -LiteralPath 'C:\Users\33076\Desktop\高级开发'
Get-Content docs\AI_PIPELINE_PILOT_20260912.md -Raw
Get-Content experiments\diagnostics\visibility\germany-20260912-v2\review_status.json -Raw
```

模型相关改动完成后运行`.\scripts\run_tests.ps1`。旧训练checkpoint的trainer签名已变化，不绕过签名resume。

## 2026-08-30 19:24 唯一当前断点（以下全部旧步骤为历史）

**最后完成步骤**：AI Pipeline Diagnostic Sprint完成；GN2/4/8固定patch记忆通过；原BN因果干预与历史完整模型反证完成；空间/类别/分辨率/采样审计完成；最终run_tests.ps1退出0。没有关闭新的业务gate，仍4/9。

**当前实验PID**：无。原BN诊断PID13360已完成，GN诊断也完成。不得重复启动同一输出目录或启动第三轮完整训练。

**实验日志**：logs/diagnostic-overfit-v1.log、logs/diagnostic-overfit-groupnorm-v1.log、logs/diagnostic-baseline-regression.log、logs/diagnostic-final-regression.log。

**最新checkpoint**：experiments/diagnostics/overfit/groupnorm-20260830-v1/patches-8/best_model.pth，SHA256=92e06fa0121297a395f8ae32df38334438fc61938518fc7f1668836e6daf78dc。仅诊断，GN架构不是当前API旧BN，禁止直接替换线上。历史正式研究候选仍models/checkpoints/full-germany-tempered-20260830/best_model.pth（SHA见FINAL_ACCEPTANCE_REPORT）。没有production候选。

**最后测试结果**：AI8、项目脚本33、训练11、Java17核心53、HTTP1、Java21SDK55、注册探针通过，联合退出0。GN重载概率一致，FP32单样本/批量最大误差≤1.41e-6；TF32初始失败证据保留。未做新增GUI业务验收。

**先读取**：docs/AI_PIPELINE_DIAGNOSIS.md、docs/LABEL_ALIGNMENT_AUDIT.md、docs/RESOLUTION_EXPERIMENT.md、docs/FINAL_ACCEPTANCE_REPORT.md、docs/GIS_VALIDATION_BOUNDARIES.md、experiments/diagnostics/reports/historical_bn_control.json、runtime/competition-readiness-evidence-20260830.json。

**下一步具体工作**：

1. 建立Germany train/validation逐tile可见性审阅清单（post1/post2来源、云影/无效区域及拒绝原因），按源影像证据制定质量筛选规则；禁止根据Louisiana指标选择规则。当前valid只剔nodata，不能当云mask。
2. 对可见地物建立配准控制点残差证据；40/40地理覆盖一致不等于地物配准全部通过。
3. 将已验证GN作为独立研究架构/元数据版本接入训练与候选推理，保持旧BNcheckpoint拒绝不匹配；不得只在旧服务使用model.train()。完成小规模train/validation对照后再决定EXP-A/B，不能直接40epoch。
4. 使用experiments/diagnostics/sampling/positive_sampler.recommended.json的策略作为参考，不能直接传给train_full；文件diagnostic_only会主动拒绝。sampler实际重复采样覆盖损失在sampler_audit.json明确记录。
5. 新split必须披露旧数据使用史；当前599 Louisiana不是未见盲测，不能事后改名。正式阈值需真实批准，config/model_acceptance.yaml当前故意未批准；不要降低门槛转绿。
6. GIS完整gate仍需全洪水范围/社区人口及20建筑原生独立核验；GT结构并集不当洪水范围。真实资源容量/来源和完整授权GUI业务未验收，不生成RC1。

**下一步命令（先核对证据，不启动训练）**：

```powershell
Set-Location -LiteralPath 'C:\Users\33076\Desktop\高级开发'
Get-Content docs\AI_PIPELINE_DIAGNOSIS.md,docs\LABEL_ALIGNMENT_AUDIT.md -Raw
Get-Content experiments\diagnostics\labels\visual_review.json -Raw
Get-Content experiments\diagnostics\sampling\positive_sampler.recommended.json -Raw
```

需要复核checkpoint时运行`.\.venv-training\Scripts\python.exe app\training\verify_overfit_checkpoint.py`；改完下一阶段代码后运行`.\scripts\run_tests.ps1`。注意trainer源码签名已因新增采样器改变，旧checkpoint resume会拒绝；不要绕过签名。

## 2026-08-29 唯一当前顺序（下方为历史）

1. 管理员授权宿主加载已更新target插件，选择 `data/demo/dispatch-spacenet8-endpoint-v2` 新建演练路网；必须得到 `length_weight_verified=true` 和 `exercise_routes_verified=true`。读取失败JSON继续修复，不复用旧数据库。
2. 用本次有效 `network-build.json` 运行 `scripts/audit_competition_readiness.py --network <文件>`，保存门禁报告。
3. 提供或导入赛事认可的跨区域独立测试数据、人口/社区数据和真实/认可资源台账；没有这些输入不得编造精度、人口或实际资源。
4. 在MapGIS内完成配准图层渲染、实体/面积统计、真实路网规则和完整报告现场验收，再将对应证据字段置为true；不得手工编辑JSON绕过门禁。

## 最新：道路线类create重载修复

用户宿主复测已成功创建并打开HDF数据库，证据mapgis-74b9c4d4-4815-4a09-9b4d-506d3e6a27d3/network-build.json包含真实database_url；失败为创建道路线类返回0。根因：SFeatureCls.create(String,GeomType)参数是完整URL，之前误传普通类名exercise_roads。官方CreateDataDialog使用绑定数据库的五参数create(name,type,dsID,srID,fields)。现改为create("exercise_roads",GeomType.GeomLin,0,geographicId,null)，移除事后setSRef，增加类打开校验、导入数量一致性、当前源道路和精确阶段证据。

runtime/road-create-fix-build成功，Java40及SDK注册通过，javap确认实际调用五参数重载。运行中宿主仍旧JAR，需保存工作后管理员stop_demo/build_mapgis_plugin/start_demo部署复测。尚未验证道路线导入、投影和建网，不宣称原生通过。新问题不是DLL/授权/数据库名称问题，不要重复排查已通过步骤。


## 最新：数据库创建名称修复（用户宿主实测后）

用户在授权桌面点击建网，已通过DLL初始化及Server.connect，实际失败在createGDB返回空/未打开；证据mapgis-f5fd1601-5cb9-410e-9a8e-0afc67ac3ef0。发现明确代码缺陷：FG_Exercise_+UUID无横线为44字节，而官方CreateGDBDialog.validateDBName限制32字节。已改为FG_+24位UUID共27ASCII字节，新增2项测试；改用官方GDBCreateParam/DBFileInfo/FileExtendInfo本地HDF参数（10MB初始，2MB增长），不再使用旧三字符串接口及无用.log路径。新增名称/服务器类型/文件路径/阶段证据，区分空对象和未打开。

runtime/db-create-fix-build编译及Java40项通过，SDK注册通过。正在运行的宿主尚未载入修复版；不要宣称原生创建已验证。保存关闭后管理员stop_demo、build_mapgis_plugin、start_demo再运行建网。当前证据不能证明许可失效。新一轮若失败读取network-build.json的stage和详细参数，不再重复DLL排查。


## 最新：2026-08-28 16:33 用户授权自行创建联调数据

不再向用户索要道路/资源文件。scripts/prepare_dispatch_data.py已实际生成data/demo/dispatch-spacenet8：真实官方0_41_59瓦片20条道路、82建筑，3组明确scenario_only/is_real_asset=false的车辆，需求12人、30km/h及closure为演练假设。没有伪造网络ID。源文件SHA256验证与几何保真、拒绝覆盖测试通过，脚本合计15项。

配套512x512 EPSG4326配准影像已创建data/processed/geotiff-test-0_41_59/pre.tif和post.tif。该瓦片属于训练集，只做业务联调不能当独立精度验证。prepare_geotiff_fixture新增--label参数，旧默认保留。

MapGisExerciseNetworkBuilder与面板“创建演练路网”入口已实现并构建到实际target插件，Java38和安装SDK注册通过。只建新UUID数据库，官方SDK导入道路/投影/NetCls.create/源要素子边映射。独立JVM实际尝试在ServerNative.jni_CreateObj前DLL初始化失败，data/demo/dispatch-spacenet8/mapgis-native-attempt-20260828/network-build.json明确native_network_created=false。尚无可用NetCls文件。不能宣称建网成功。后续需授权宿主运行该入口，修复实际原生问题，再补分钟权、资源节点绑定、核查跨CRS处理及自动演练DispatchRequest；resources.json现阶段不是可直接导入的DispatchRequest。


## 最新：2026-08-28 16:24，联动/调度/报告已实现，仍未完整验收

不要重做：RoadClosurePlan、DispatchRequest、MapGisRoadNetworkMapper、DispatchPanel、HtmlOperationalReport 已添加；ExposurePanel接入调度。JSON导入真实资源和核查证据，目标/类型/需求可选，结果表与报告包含原始模型预览和空间清单。UNREVIEWED拒绝出调度；CLOSED所有子边阻断。没有全域交通管制或轻重淹权重，不是真实派单。

原生SDK独立批处理实际失败两次，证据runtime/native-raster-20260828a/b/native-acceptance.json；DLL初始化失败，不等于许可失效。新宿主内“原生栅格验收”按钮复用同一真实测试。当前会话非管理员，无桌面进程；已成功更新target插件。需要获授权宿主上下文及真实NetCls/资源/核查输入才能推进原生业务终验；不能编造数据通过。

训练：下载sample --count18成功55对象。新3m道路缓冲（研究环境shapely2.1.2/pyproj3.7.1）、有效像素掩膜、balanced BCE+Dice、256px40轮已跑完。config/training.balanced18-stratified.json → models/checkpoints/spacenet8-balanced18-stratified。训练/验证/测试10/4/4；首次划分验证集缺受淹建筑，训练前交换新下载train/val瓦片后全部类别有覆盖，测试集未变。旧初始config未训练，保留coverage审计。最终same4test比较见balanced18-comparison.json：受淹建筑IoU .0261→.1202，道路0→.0490，仍很差。不要宣称达标或自动替换在线模型。

config/application.balanced18.yaml只作候选测试；scripts/verify_research_model.py真实CUDA API成功，data/outputs/balanced18-api-20260828/verification.json。新增模型身份按权重SHA256；/model/info不再错误返回fallback版本。当前8765服务未重启，仍旧模型。

最新验证：run_tests.ps1 -E2EPort18765整体成功（AI当时6，后增身份测试共8）、脚本13、Java38、HTTP1、SDK38+注册；训练8；新模型GPU API通过。首次整体回归因8765占用失败，已把测试默认独立18765，不关闭现有服务。代码已在真实target构建。

下一步：在授权宿主跑真实RasterToPolygon、实体查询和网络路径测试，修复实际运行问题；准备真实投影NetCls及分钟权与道路来源，补动态权/已有阻断与完整灾损统计，完善报告；扩大跨区域训练/预训练与独立质量验收。当前不是全部完成。

## 最新：实体核查桌面接入与多资源分配（2026-08-28 13:02）

新增ExposurePanel并接入识别面板“建筑／道路核查”：空间化后生成或复用原生斑块，列出当前地图顶层建筑面/道路线图层（GeomReg/GeomLin），通过MapLayer.getData及getSrefInfo读取实际数据与CRS，原生相交查询、去重、逐实体JSON展示、HTML报告导出。未选择两类实体、缺URL/CRS、网格不符均拒绝。此UI与原生查询仍未运行验收，不能宣称全部功能完成。

ResourceDispatcher新增多资源容量分配计划及未满足需求数，不执行调度、不修改容量；重复资源ID拒绝。RouteResult增加非空节点/有限非负距离和时间及防外部修改校验。

runtime/integrated-build成功，Java31项、Python13项及插件注册检查通过。用户仍要求统一完成后再测试，不逐轮重启。待办：真实建筑/道路载入与原生查询验证，网络边映射/阻断规则/动态权重、调度GUI、完整报告、有效模型与统一发布；现阶段不是全部完成。

## 最新：实体暴露统计基础与核查报告（2026-08-28 12:56）

用户明确要求全部功能整合后再测试，不再每轮要求管理员重启。继续独立目录构建，不关闭运行桌面。

新增ExposureAssessment：命中按数据集+实体ID+类型去重，保留斑块证据，计候选建筑/道路，不计作已损毁/阻断。HtmlExposureReport提供转义的逐实体清单，未计算面积、人口、阻断和路线明确标未知。MapGisExposureQuery通过本机SFeatureCls.query、QueryDef.setSpatial(ModeIntersect)实现原生精确相交适配，调用方必须传入已核对一致的坐标系，数据集借用不修改；失败不会当零命中。此适配层未接GUI、未实际原生查询验收，不能标成完整统计完成。

runtime/exposure-build编译通过，Java29项（含去重、证据保留、报告转义测试）。下一步接实体数据选择与真实CRS读取，原生空间查询后将结果接报告/道路核查；再接入路网及资源调度。沿用用户最终统一验收要求。

## 最新：原生矢量斑块导出（2026-08-28 12:48）

核验outputs/f29281d2cca54885940d3f3e5466fb64/mapgis-e13e68e7-fcde-4184-836d-3d9ff877ec93/spatial-result.json及六份TIFF：均512×512、EPSG4326、与灾前网格一致，overlay为RGB。非空flood_mask/flooded_building仍为palette，Gray设置未完全持久化；不能声称所有单波段显示已修复。用户截图证明RGB地图显示。

新增“导出受淹斑块”按钮，空间化后使用本机MapGIS RasterBand.getPixelPlane、RasterToPolygon.run、Geometry.toGeoJson，背景0排除；只接受EPSG4326、<=1048576像素二值掩膜。导出GeoJSON严格校验Polygon、闭合环、源网格范围；只称model_patch_count，不冒充建筑栋数/完整洪水面积。文件CREATE_NEW不覆盖，错误写日志。原生矢量化尚待管理员宿主运行，不能以编译代验收。

独立runtime/vector-build编译通过，Java26项、Python13项与SDK注册检查通过。下一步保存工作并管理员stop_demo/build_mapgis_plugin/start_demo，识别、空间化后点击导出受淹斑块，检查GeoJSON或错误日志；随后接建筑/道路实体与斑块叠加。不把本次矢量斑块功能当作完整灾损统计完成。

## 最新：分类空间结果集（2026-08-27 21:46）

新增MapGisSpatialResultSet：先核对两期网格，四类掩膜+合并掩膜+RGB叠加共六份TIFF由MapGIS逐份转换、重新打开并检查网格；完成后才写spatial-result.json。每次新结果生成独立UUID目录，失败不写成功清单，不覆盖已有证据。面板加载流程已接入，重复点击复用该结果集。SpatialResultManifest记录输入、原始模型结果、输出路径、MapGIS读取的空间参考和网格，明确map_rendering_verified=false、damage_analysis_completed=false、production_ready=false。

独立构建runtime/spatial-set-build通过，Java23项、Python13项、安装SDK注册/启用探针通过。此轮是分类输出准备，不是灾损统计完成。当前管理员桌面仍持有旧插件，尚未运行新版六份批量空间化。需保存工作后stop_demo/build_mapgis_plugin/start_demo，再重新识别并加载，将spatial-result.json及显示结果用于下一轮真实验收。后续需针对建筑/道路矢量完成MapGIS空间叠加与路网联动。

## 最新：实际输出审计与地图对照（2026-08-27 21:32）

读取用户真实MapGIS生成的flood-georeferenced TIFF：512×512、EPSG4326，仿射变换与输入一致，像素0/255正常；但colorinterp=palette且colormap报NULL color table。这是实际显示隐患，不再把坐标生成视为失败。代码新增原生Gray解释设置，掩膜保留供分析；地图改显示空间化RGB预览，并加载灾前/灾后供三按钮切换。重复同一结果复用输出路径，图层按URL去重；不删除用户已有重复图层。原生网格检查和输出复核通过RasterGrid元数据检查接入，不自行实现GIS变换。

独立构建runtime/map-display-build成功，Java20项、Python13项与真实SDK注册/启用检查通过。当前旧桌面占用target JAR，新版实际原生渲染尚未验证。用户保存工作后管理员stop_demo/build_mapgis_plugin/start_demo，再重新识别、空间化、切换三种地图。若失败看logs/desktop.log，不宣称全部完成。后续仍需道路匹配、MapGIS空间灾损统计/网络权更新、调度与完整报告GUI；模型精度未达标。

## 最新：模型提示、GeoTIFF夹具与标签修复（2026-08-27）

面板异步查询实际health后端/设备，不再硬编码fallback或“尚待授权”；普通PNG禁用空间化，图层添加后restoreWnd。隔离科研环境准备512×512 EPSG4326同网格TIFF，真实CUDA API任务96603ce9bbec4d999ab76f79d572b748成功，详见docs/GEOTIFF_TEST.md。当前运行桌面锁定旧JAR，runtime/model-status-build为独立构建；实际MapGIS空间化和显示仍需管理员重启后的现场验收。

训练发现并修复flooded=null被错误忽略：官方baseline将其视为未受淹。旧报告标签语义错误，不再作为精度依据。train_full签名增加预处理哈希；新config/training.label-fix.json独立训练40轮，非受淹建筑/道路测试IoU仍0，未部署到在线服务。下一步扩充类别覆盖、官方道路缓冲与分辨率研究，不能只靠增加轮数或改阈值宣称精度提升。

## 最新：按钮禁用修复，尚待部署（2026-08-27 20:56）

宿主先isEnabled后onCreate；旧命令以application非空为启用条件，初始false被宿主缓存。已改为入口始终可用（无活动地图也应可打开），点击时检查初始化并显示错误，面板异常输出日志与提示。真实SDK探针增加初始化前可用断言。当前运行宿主锁定target插件JAR，不能替换；独立runtime/enable-fix-build构建和14项Java测试通过，SDK注册/启用探针通过，Python13项通过。用户保存工作后需在管理员窗口依次stop_demo.ps1、build_mapgis_plugin.ps1、start_demo.ps1；仅重启还不能加载本次修复。未宣称实际GUI点击已验证。

## 最新：按钮注册修复（2026-08-27 20:52）

项目宿主已实际授权通过。识别按钮无反应源于安装版插件扫描器要求入口类以com.zondy.mapgis开头且含plugin；三个入口和XML已修正，SDK真实注册探针通过，Java14项通过。build_mapgis_plugin现在强制验证命令/页签/分组注册。重启项目桌面后继续验收点击面板和真实GIS流程；旧发布ZIP尚未更新。下方授权未通过记录仅作历史参考。

## 授权排查更新（用户确认官方管理员桌面可进入）

官方开发桌面可用，优先排查项目启动环境，不再要求补授权文件。启动器已对齐 desktopjava.exe、GBK 控制台编码和 Program PATH，并要求管理员权限；12项脚本测试通过。当前非提权会话没有完成修正后的真实桌面验证。下一步在同一获授权用户的管理员 PowerShell 执行 scripts/start_demo.ps1，确认插件加载与原生GIS；退出用同窗口 scripts/stop_demo.ps1。旧ZIP不包含本次修复。

## 最新增量（2026-08-27 20:15）

新增HtmlInferenceReport和桌面导出按钮，真实GPU HTTP集成已生成带内嵌预览的识别记录；这不是完整GIS灾情报告。风险评分现在拒绝缺失/NaN/无穷和负权重。联合回归AI6/脚本10/Java14/HTTP1/SDK14通过，GPU跨进程1通过。当前最新源码尚未重新制作开发ZIP，旧ZIP不包含此次新增功能。MapGIS授权复测仍code3；待补齐真实空间业务和完整报告。

## 最新连续开发结果（2026-08-27 17:55）

已完成独立应用XML生成、真实Ribbon页面/命令、空间化按钮、start_demo/stop_demo、run_model_e2e、开发版打包和README/架构/部署/合规文档。联合回归AI6+脚本10+Java10+HTTP1+SDK10通过；真实GPU跨进程1项、训练4项通过。开发包明确不是参赛成品。

MapGIS实际--developer --custom-ui启动仍authorization_failed，所有启动进程已清理，见logs/desktop.log。继续前应由用户通过官方管理员启动/云授权管理确认授权，不能绕过。恢复后优先验证Ribbon加载、空间化实际坐标，再接入路段匹配/权更新/空间统计/资源/报告完整GUI。现阶段模型IoU0、GIS闭环未完成，不能标记项目完成。

## 当前连续开发进度（2026-08-27 17:45）

不要按旧段落重做已完成工作。官方Germany六组已下载；独立GPU烟测+模型重载+FastAPI TestClient真实模型推理通过。配置训练2轮+恢复第3轮、独立留出测试也通过；IoU仍0，不代表模型精度。

最新回归：AI6/脚本5/Java核心10/HTTP1/SDK10；科研训练unittest4。MapGisRasterSpatializer和MapGisNetworkRouter真实API适配层编译通过，尚未宿主运行；路由还需路段匹配、动态权更新与GUI联动。MapGIS官方开发启动仍authorization_failed，verify脚本现在准确返回3（双编码原始日志），不能把进程存活标通过。

下一步：完善插件注册/Ribbon入口、接入空间化按钮和业务面板；完成一键启动/关闭、配置和发布；实现真正灾损空间统计/路线/报告串联（许可恢复后必做真实GIS E2E）。继续完善AI训练质量、官方道路标签缓冲预处理。所有原生API从本机 Program/MapGIS_Java_Api Javadoc与JAR确认。

2026-08-27：资源推荐业务层与输入校验已实现，总回归 Python 3 / Java 17 8 / HTTP 1 / Java 21 8 全通过。云开发授权已识别但验证失败，见 BLOCKERS.md 更正。后续优先接入官方 MapGIS 网络分析实现路线提供器、完成官方 SpaceNet8 样本和训练链路，并完善桌面交互。不要把自写路由和合成影像当成参赛验收结果。

已完成工程骨架、环境、上游锁定、AI fallback 服务、Java/Python 通信、风险与安全路径核心，以及基于本机真实 SDK 的 MapGIS Java 21 插件编译和打包。

最后一次联合回归：Python 3 passed；Java 17 核心 6 passed；跨进程真实推理 E2E 1 passed；MapGIS Java 21 Profile 6 passed并生成 `app\mapgis-flood-desktop\target\mapgis-floodguard-plugin.jar`。MapGIS 宿主实际启动已到达授权验证阶段，但缺少匹配许可，见 `BLOCKERS.md`。下一步继续把灾损统计、安全路线和 HTML 报告串入演示输出，并完成下载/训练脚本；许可补齐后立即执行宿主插件可见加载与结果图层测试。

继续工作前依次阅读：`README_CN.md`、`PROJECT_STATUS.md`、`NEXT_TASK.md`、`BLOCKERS.md`、`docs/DEVLOG.md`。

## 2026-09-12 下一步：道路类别诊断

人工审查和两组正式训练已经完成。不要重复审查或直接延长训练。下一步按冻结的 98/18 Germany 划分执行道路标签诊断：抽取含道路/受淹道路的训练和验证样本，核对栅格化缓冲宽度、有效像素掩膜、每图道路像素占比及影像可见性；随后只做一个能同时约束普通道路与受淹道路的最小对照实验。不得读取 Louisiana/test 选择模型，也不得把当前检查点部署为生产模型。

## 2026-09-12 阈值诊断后的下一步

道路标签存在，主要故障是模型道路概率低于固定0.5阈值。已生成研究校准副本，但校准与报告使用同一Germany验证集，不能作为最终精度。下一步需要建立新的独立区域验证证据，或在不读取Louisiana既有研究测试的前提下冻结新的Germany空间留出；在此之前不部署校准候选。

两折折外校准已完成，macro IoU 0.11405；它减少同集拟合偏差，但受淹类别样本过少，不能替代独立区域评估。不要继续在这18张图上反复调阈值。
## 2026-09-12 Two-stage feasibility之后的唯一模型任务（当前状态）

本轮Stage1 + Oracle Stage2已经完成并停止。证据符合CASE A。下一模型阶段如获授权，仅开展Predicted-Gate Integration：冻结本轮Stage1/Stage2产物，定义Stage1预测gate到status head的组合规则，量化相对Oracle的error propagation，并继续只用Germany development数据。不得自动启动；不得读取Louisiana或future blind holdout；不得替换production模型；production_ready=false。
## 2026-09-12 Predicted-Gate之后的唯一模型决策（当前状态）

Predicted-Gate已完成，结论PG-B，未创建`two-stage-predicted-gate-v1`。下一步只允许二选一：A）做一次严格限定的Stage1 object segmentation专项改善，冻结Stage2与本轮阈值/评价规则，再复测error propagation；B）停止架构研发并保留germany-reviewed-v1，等待未来独立blind evaluation条件。不得自动开始新loss、sampler、backbone或Experiment；不得读取Louisiana/future blind holdout；production_ready=false。
## 2026-09-12 Stage1 Road Gate审计后的当前任务

Road Gate Miss Audit不支持高分辨率假设，Stage1-E未启动，`model_research_phase_paused=true`。停止模型实验并切换到非模型验收工作：Gate 5、Gate 8、Gate 9。继续保护Germany frozen split、Louisiana和future blind holdout；不训练Experiment F、不搜索loss/sampler/backbone/threshold，不修改Stage2或production模型。development baseline保持germany-reviewed-v1。
