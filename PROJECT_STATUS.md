## 2026-10-05 自主精度核查

两张 Louisiana-East 训练影像 249 个对象已完成 AI 辅助逐对象影像查看：75 个受淹复核、174 个证据不足；未产生新独立真值。E4 固定互斥输出规则完成一次预注册开发验证，macro IoU 0.160657→0.113292、受淹道路 IoU 0.073678→0，按门槛拒绝，线上模型未替换。独立精度和生产就绪状态仍未核验。详见 `docs/AUTONOMOUS_ACCURACY_AUDIT_20261005.md`。

## 2026-10-04 灾损专题图模块

已接入 `flood_prediction.json` 输入契约、四类 MapGIS 原生 HDF 要素/专题符号、对象点击属性和导入/选择证据导出。SDK 构建及 60 项测试通过。当前会话无法运行授权 MapGIS 宿主，原生渲染、点击和真实截图待现场验收，readiness 仍为 4/9。详见 `docs/DAMAGE_THEMATIC_20261004.md`。
## 2026-10-04 桌面工作台开发进度

已新增 `FloodGuardMainWindow`，使用 MapGIS 官方 `MapControl` 作为中央地图，提供七项菜单、六类图层入口、指标面板、日志及截图/JSON/日志证据保存。现有识别、实体核查和原生网络调度面板已接入统一地图上下文。SDK 56 项、插件注册/构建和桌面脚本 9 项通过。当前非管理员会话使官方宿主在启动前停止，真实 GUI 截图与现场终验尚未取得；Gate 5/9 及 readiness 4/9 保持不变。详情见 `docs/DESKTOP_WORKSPACE_20261004.md`。

## 2026-09-26 SpaceNet-5 外部预训练迁移已审计并停止 head-only 路线（当前 AI 状态）

- 从官方 SpaceNet S3 下载 XD_XD SE-ResNeXt-50 U-Net fold0，原始 301,620,821 字节、SHA256=`716c4fa3...6daa783`；转换为纯 state_dict，SHA256=`f3201bb8...134b269`，402 张量全部严格加载，512 CUDA 前向通过。
- 固定 0.5 零样本道路对象 IoU 仅 0.012310，不能直接作为道路 gate。
- 预注册 697/18/0、10 epoch 的冻结主干+六通道 head 实验完成；最佳第9轮 building/road/mean IoU=0.012889/0.128205/0.070547，独立重载一致。
- 现有 E3c mean=0.290088，候选低 0.219541，故 `decision=stop_head_only_transfer`、`promotion=rejected`；不解冻后在已揭示验证集继续搜索，E4 research leader 不变，Louisiana-West 未使用。
- 联合回归通过：AI 9、脚本48、训练91、Java17核心54、真实HTTP1、Java21 SDK56及插件注册/构建。详见 `docs/SPACENET5_PRETRAINED_TRANSFER_20260926.md`。

## 2026-09-26 因子化对象/状态实验已拒绝（当前 AI 状态）

- 新增对象存在概率 × 对象内洪水状态概率的四类分解，0.5 阈值下建筑和道路状态输出都严格互斥；对象 BCE 覆盖全图，状态 BCE 只监督对象像素。
- 首个 `x=16..18` 协议因道路缓冲交叉产生少量真值重叠而在候选首步失败关闭；未保存候选 checkpoint、未读取候选留出指标。因基线指标已揭示，该折作废而未重跑候选。
- 在训练前重新冻结未评估的 `x=13..15` 空间折（592 train/105 final-only holdout）。独立二元基线 macro IoU 0.051853；因子化候选虽把状态重叠降为 0，但 macro 仅 0.000783，四类全部退化，`promotion=rejected`。
- 两个 checkpoint 已独立重载复算，前 13 轮留出读取为 0；未使用 Louisiana-West，未替换 E4，`production_ready=false`。详见 `docs/FACTORIZED_STATUS_SPATIAL_FOLD_20260926.md`。

## 2026-09-26 Louisiana-West 无标签盲推理已完成（当前 AI 入口）

- 新增 `scripts/freeze_external_test.py`：在任何模型推理前冻结发布者、原始来源、许可证及本地证据、事件/区域、配对表、全部文件 SHA-256、四类 feature 支持、两个 checkpoint 和固定 0.5 协议。
- 冻结器已对当前真实开发数据建立 footprint 参考目录：Germany 116 + Louisiana 599，共 715 张且灾前影像 SHA-256 全部唯一；外部 test 与任一已用影像相同或存在正面积空间相交都会拒绝。
- 新增 `scripts/evaluate_external_test_once.py`：只允许对封存 manifest 运行 E4 与旧域平衡基线的同样本一次性对比；禁止训练、阈值校准和 checkpoint 选择，已有输出拒绝覆盖。
- 本机已发现官方 Louisiana-West public test，406 条 pre/post1 配对完整、无公开 GeoJSON 真值；与现有 715 张开发影像的哈希重复和正面积空间相交均为 0。
- 已在冻结全部输入、E4 checkpoint、512 尺寸和 0.5 阈值后完成一次性 CUDA 推理。四类均有响应，但受淹道路预测 100% 同时属于未淹道路，受淹建筑约 99.56% 同时属于未淹建筑，暴露出独立 sigmoid 状态通道非互斥问题。
- 没有真值，故 IoU/F1/precision/recall 均为空，`accuracy_verified=false`、`production_ready=false`；该 test 永久禁止用于训练、校准或选模。详见 `docs/LOUISIANA_WEST_BLIND_INFERENCE_20260926.md`。

## 2026-09-26 空间外推与建筑状态实验已闭合（当前 AI 状态）

- Louisiana-East `x>=22` 的 92 张 final-only 空间留出已完成无泄漏重做。随机基线 macro 0.088266；fold-safe foundation 初始化 macro 0.138277，提升 0.050011，但受淹建筑 IoU 0.040006→0.026148，退化 0.013858，超过预注册容忍度，故 `promotion=rejected`。
- fold-safe foundation 从随机权重训练，foundation train/selection 与空间留出交集为 0；下游检查点独立重载一致，SHA256=`682ed3cdd80482dae82d67eb439de3a9b9b7dc52a70140a08bfdedf0ed9e1ab9`。
- 在全新 Louisiana 中部 `x=19..21` 的 106 张空间折上，互斥建筑状态候选 macro 0.045533，低于独立二元基线 0.076732，且受淹建筑 IoU 0.151166→0，`promotion=rejected`。不得在该折继续调阈值或 loss 权重。
- E4 仍是 Germany 开发集 research leader（macro 0.160657）；没有任何空间实验或候选替换线上模型。外部独立 test 仍缺，`production_ready=false`。详见 `docs/LOUISIANA_SPATIAL_HOLDOUT_20260926.md` 与 `docs/BUILDING_STATUS_MIDDLE_FOLD_20260926.md`。

## 2026-09-26 Louisiana-East 空间条带验证（首轮已因初始化泄漏作废）

- 已排除反复使用的 Germany 18 张 validation，并从原训练池冻结 Louisiana-East `x>=22` 连续空间条带 92 张；其余 605 张训练。两组固定 14 epoch，`validation_schedule=final_only`，最后一轮前不读取空间 holdout。
- 随机初始化四类 IoU 0.15778/0.04001/0.14825/0.00703，macro 0.08827；foundation 初始化为 0.25371/0.03251/0.26406/0.05758，macro 0.15196，提升 0.06370。
- 泄漏复核发现 E3c 初始化 checkpoint 曾用全部 Louisiana 训练，已见过这 92 张。故 foundation 列虽重载复算一致，但不是泛化证据，已明确改为 `promotion=invalidated`；随机初始化 macro 0.08827 仍是有效固定轮次基线。
- 正在用完全排除该条带、从随机权重训练的 fold-safe foundation 重做对照。该空间验证仍不是未来独立 test，`production_ready=false`。报告见 `docs/LOUISIANA_SPATIAL_HOLDOUT_20260926.md`。

## 2026-09-26 Foundation 初始化四类模型已晋级（当前研究状态）

- E3c 单影像 U-Net foundation 最佳 epoch 28：建筑/道路 IoU 0.28436/0.29581，均值 0.29009；相对旧四类模型对象并集基线 0.24110 提升 0.04899，独立重载一致，`promotion=accepted`。
- E4 将 foundation 的 84 个兼容张量迁移到四类 SiamUnet_diff，仅重建输出层；30 epoch 最佳 epoch 14，固定 0.5 四类 IoU 0.22571/0.11623/0.22702/0.07368，macro 0.16066。
- 相对上一 research leader macro 0.14390 提升 0.01676（11.65%），四类全部提升，`promotion=accepted`。新 checkpoint SHA256=`ba2da68622d79683de2b6a9c30209c509d21cc44c1693e9118a061616c93e4bc`。
- 预注册的 0.25 温和 soft gate macro 降至 0.15677，`promotion=rejected`；不在同一 validation 搜索 gate strength 或阈值。
- 新模型仍仅是开发验证 research leader；test 为空，`production_ready=false`，未替换线上模型。报告见 `docs/FOUNDATION_AUXILIARY_EXPERIMENT_20260926.md` 与 `docs/FOUNDATION_INITIALIZED_FOUR_CLASS_20260926.md`。

## 2026-09-26 E2 原分辨率裁块已完成

- 已生成 715 组 1280×1280 compact 对齐缓存，并完成 448 crop、336 stride 重叠推理的 30 epoch 单变量实验。
- 旧 512-trained 模型在同一 1280 tiled 口径 macro 为 0.05251；E2 最佳 epoch 29 四类 IoU 0.10565/0.00012/0.01431/0，macro 0.03002，明显退步，`promotion=rejected`。
- 独立进程重载复算一致。停止继续搜索 crop/stride/epoch；512 非 EMA 域平衡模型继续作为 research leader。报告见 `docs/NATIVE_CROP_EXPERIMENT_20260926.md`。下一步为 512 foundation 辅助监督。

## 2026-09-26 E1 EMA 已完成

- 在当前域平衡基线上完成 EMA-only 30 epoch 对照；最佳 epoch 28，固定 0.5 四类 IoU 为 0.21486/0.10365/0.19811/0.05879，macro 0.143853。
- 非 EMA macro 为 0.143899；EMA 低 0.000046，且未淹道路退化 0.01130，未满足预注册晋级门槛，`promotion=rejected`。独立进程重载复算一致。
- 不在同一 validation 上继续搜索 decay；非 EMA checkpoint 保持 research leader。报告见 `docs/EMA_EXPERIMENT_20260926.md`。下一步为 E2 原分辨率裁块与重叠推理，test 仍为空，`production_ready=false`。

## 2026-09-26 域平衡训练与开源算法检索

- Germany 98 + Louisiana-East 599 的 1:1 域平衡、域内正类感知训练已完成 30 epoch；最佳 epoch 30，Germany 18 张开发验证固定 0.5 四类 IoU 为 0.20785/0.10421/0.20941/0.05412，macro 0.14390。
- 相对 2026-09-16 普通合并训练 macro 0.12250 提升 0.02140，但两类道路回落；说明域偏置缓解，建筑/道路竞争仍未解决。独立进程重载 checkpoint 复算一致。
- 当前 checkpoint 仅是开发验证口径的 research leader；test 仍为空，`production_ready=false`，未替换线上模型。报告见 `docs/GERMANY_LOUISIANA_DOMAIN_BALANCED_20260926.md`。
- 已完成 SpaceNet 8 前五名、SpaceNet 5、CRESI、CoANet、ChangeFormer、BIT-CD、FADS-Fusion 等一手开源方案检索和许可证筛选。适配路线为 EMA → 原分辨率裁块/重叠推理 → foundation 五辅助通道 → soft-gated Siamese flood；详见 `docs/OPEN_SOURCE_ALGORITHM_ADAPTATION_20260926.md`。

## 2026-09-16 Germany + Louisiana-East 新模型研究训练

- 按用户要求，在独立配置中将 Louisiana-East 599 组带标注样本加入德国冻结 train 98 组；德国 validation 18 组保持不变，test 尚未下载，`test=[]`。源文件按先前完整审计逐项哈希复核。
- 30 epoch 已完成；最佳 epoch 25，德国验证固定 0.5 阈值四类 IoU 为 0.12824/0.05272/0.22751/0.08152，macro 0.12250。两类道路改善、两类建筑下降；重载 checkpoint 复算一致。
- 新模型仅为 research candidate，不替换 Germany-only 开发基线或线上模型；`production_ready=false`，无独立 test IoU。详情见 `docs/GERMANY_LOUISIANA_EAST_RESEARCH_20260916.md`。Gate 5 仍 BLOCKED、readiness 仍 4/9。

## 2026-09-12 Gate 5 Closure Phase 2（当前状态）

- 固定 AOI 已由 BKG 官方 VG250-EW WFS 确认为 Dernau Gemeinde（AGS 07131017），不是根据 EPSG 猜测；行政面完整覆盖 AOI。
- 真实 community 数据已固定：BKG VG250-EW 2024；真实 population 数据已固定：Destatis Zensus 2022 官方 100m 格网。15 个有值格网相交 AOI，参考估算 AOI 人口 125.182、受影响人口 115.077。
- Phase 1 实体值保持 82/76 建筑、20/14 道路、12,281.684 m²、2,446.522 m；continuous flood area 和 blocked road count 继续为 null。
- GUI 已加入明确 GT VALIDATION/AI PREDICTION 模式，GT 禁止 AI 推理；Java21 SDK 56 项和注册 probe 通过。
- 当前 MapGIS GUI 无可绑定 native app 接口，且正式风险仍缺可追溯道路/医疗可达性等完整指标。validator 退出2，Gate 5 仍 BLOCKED，readiness 仍4/9。详见 `docs/GATE5_FINAL_ACCEPTANCE.md`。

## 2026-09-12 Gate 5 真值闭环执行结果（Phase 1）

- 已固定 `data/acceptance/gate5-v1`，仅用于 `GROUND_TRUTH_VALIDATION`；逐文件 SHA-256、CRS、范围、来源、许可和对象级洪涝语义均已记录。
- 德国 `0_41_59` 参考分析完成：建筑 82/受淹 76，道路 20/受淹 14；EPSG:32632 计量的受淹建筑占地 12,281.684 m²、受淹道路长度 2,446.522 m。
- 已生成 JSON/HTML/两类各20条抽样核查及失败关闭校验；校验器按预期因社区、人口、风险和 MapGIS GUI 证据缺失返回非零。
- Gate 5 状态为 BLOCKED，readiness 保持 4/9。对象级 flooded 标签没有连续洪水面语义，也不证明道路封闭；缺失量不记为0。
- 当前 UI 自动化环境没有可绑定的 native MapGIS 应用接口，因此没有伪造 GUI 截图或日志。完整记录见 `docs/GATE5_COMPLETE_DAMAGE_ANALYSIS.md`。

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

以下较早日期记录仅为历史；以本节为准。

# MapGIS-FloodGuard 项目状态

## 2026-09-12 13:37 Germany 人工可见性审查工具

- [x] Germany visibility review tool：独立 `tools/visibility_review` FastAPI/HTML/JavaScript 工具，仅监听127.0.0.1，未耦合AI服务或MapGIS插件。
- [x] Persistent manual review：新决定先append-only写入reviews.jsonl并fsync，再原子更新review_state.json/summary.json；每20次派生备份、最多10份；旧20条记录只读兼容，SHA256保持不变。
- [x] Preview cache：197个样本全部预热，PRE/POST1/POST2保持宽高比，按各自CRS/transform生成建筑、道路及受淹overlay；0个缓存错误，不改GeoTIFF/标签。
- [x] Resume workflow：默认首个pending，其次needs_review；筛选、sample_id搜索、风险排序、快捷键及刷新/停服重启恢复已在独立sandbox浏览器实测。
- [x] Review integrity checker：真实manifest 197项、474个影像SHA256全部核对，重复ID/文件/映射/review/schema校验0异常，报告已生成。
- [ ] Germany visibility review complete：仍为accepted8、rejected12、pending177；`review_complete=false`，`training_split_frozen=false`，未启动训练。

## 2026-09-12 12:48 正式AI管线贯通与小试验（优先于下方历史）

- GroupNorm已从诊断提升为训练与AI服务共用的模型构造选项；旧BatchNorm checkpoint继续按明确默认兼容，结构不匹配会拒绝加载。
- checkpoint及`GET /model/info`现真实暴露model_id、architecture、normalization、SHA256、阈值、训练时间、metrics文件、git commit和split hash。GN研究checkpoint真实CUDA API推理通过，accuracy_verified/production_ready仍为false。
- Germany 10/4、12 epoch完成三组有限对照，均未读取test/Louisiana：GN+采样+加权最佳macro IoU .012844，GN+采样 .004641，GN+加权 .004912，均不具备候选价值。
- 训练器默认拒绝同时启用正类采样与正类加权，防止重复再平衡；每个split条目可显式选择官方post1/post2，选择非法或文件缺失即拒绝。
- 完成Germany train153+validation44可见性候选清单v2：197张、80张有post2、pre/post并排且记录SHA；优先Top20已逐项视觉审阅并通过结构校验，12拒绝、3选post1、5选post2，尚余177项，split未冻结。
- 完整回归：AI9、项目脚本33、训练13、Java17核心53、HTTP1、Java21 SDK55及注册探针通过。readiness重新审计仍4/9。
- 三组训练均已结束，无训练PID；未promote模型、未创建RC1。详细证据见`docs/AI_PIPELINE_PILOT_20260912.md`。
- 新增并实际运行`scripts/preflight.ps1`及`scripts/competition_acceptance.ps1`。最新自动验收包为`runtime/acceptance/acceptance-20260912-125202`，11个规定文件齐全；自动阶段完成但业务状态仍blocked/partial，competition_ready=false。

## 2026-08-30 19:24 AI诊断冲刺完成（优先于以下所有历史）

- 最低里程碑已完成：2/4/8固定patch强制过拟合、同权重BN干预、GN对照、历史模型反证、40组配准/缓存复核、796组类别统计、8组分辨率及正类采样诊断。
- 共享BN存在明确train/eval统计失配；GN固定样本四类均IoU≥90%，macro .9817/.9593/.9777，仅记忆证据。历史完整模型单改BN没有改善，不能称唯一根因/生产修复。
- 发现云遮挡仍进入valid监督、少数类稀疏；40缓存重算一致，8组无道路实体因512消失。未把地理网格一致等同全部地物配准通过。
- 正类采样器配置化可选接入；推荐片段仅诊断，不启动训练。模型离线双层验收及schema v2证据门禁完成，production_ready=false，readiness仍4/9。
- 最终完整回归：AI8、项目脚本33、训练11、Java核心53、HTTP1、SDK55及插件注册均通过；实际日志logs/diagnostic-final-regression.log。构建更新target但没有新增授权GUI业务验收。
- 全部实验已结束，无正式训练PID；没有第三轮40/80epoch、没有覆盖历史模型或数据、没有制作RC1。
- 根因和限制：docs/AI_PIPELINE_DIAGNOSIS.md；本轮验收报告：docs/FINAL_ACCEPTANCE_REPORT.md；下一步以NEXT_TASK.md顶部为准。旧DOCX未重新生成，不作正式材料交付。

## 2026-08-30 当前状态（优先于下方历史记录）

- 已审计用户解压的801组SpaceNet8数据，完成512像素缓存；153组训练、44组验证、599组跨区域研究测试，另剔除5组空间跨界数据。
- 两个40轮CUDA研究训练均结束；第二轮改用温和正类权重和验证集macro-IoU选模型。泛化精度仍不合格，未替换在线模型。
- 校准只使用德国验证集。Louisiana已重复用于研究比较，不再声称完全盲测。
- 修复分段下载恢复布局及中断合并损坏风险；隔离Java17核心测试与Java21安装SDK测试。
- 本轮核心Java53项、安装SDK55项、HTTP跨进程1项通过；Python脚本23项、AI8项、训练11项通过。SDK测试不是新增现场业务验收。
- 最新真实验收仍为4/9：原生拓扑、路权、演练封路与地图渲染已有证据；灾损分析、模型精度、生产推理、真实台账与正式业务验收仍未通过。
- 详细说明见 `docs/PROGRESS_20260830.md`；门禁证据见 `runtime/competition-readiness-20260830.json`。

## 2026-08-29 当前真实状态（优先于下方历史记录）

- [x] MapGIS 授权桌面实际完成HDF建库、20条真实来源道路导入/UTM投影、要素数据集、原生NetCls建网、关闭重开、20条源道路到20条边映射；28节点/20边证据已保存。
- [x] 道路 `mpLength` 由MapGIS写入且与原生线几何一致；默认 `NetCls.getEdgeLength` 在本SDK现场固定返回1，已从业务计算中移除。
- [x] 最新源码注册 `fg_length_metres` 比例网络权并绑定 `mpLength`，路径改用该命名权；逐边权值、路径总权、几何长度必须一致。源码/SDK构建通过，实际target插件已更新；JNI现场尚未复测。
- [x] 端点演练资源与目的地节点绑定均0米偏移；基线/封路/容量分配验收代码和JSON/HTML证据已实现。正式真实资源不以演练数据替代。
- [x] 新增 `scripts/audit_competition_readiness.py` 失败关闭门禁；当前证据1/9通过，输出 `runtime/competition-readiness.json`。Python 19项、Java 52项通过。
- [ ] 注册长度权及封路路线需在授权宿主新建数据库复测，旧数据库没有该网络权。
- [ ] 配准图层人工渲染验收、完整洪水范围/面积、实体灾损、人口/社区风险及完整报告缺少合格数据或现场证据。
- [ ] 模型仅同地区4瓦片研究比较，四类IoU约0.039–0.120；没有独立区域精度通过，不能切换production_ready。
- [ ] 缺少真实或赛事认可资源台账与正式业务验收记录；当前系统不是完整参赛交付，不得声称全部完成。

## 2026-08-28 16:33 联调数据自行创建

- [x] 用户授权后，自行生成真实道路/建筑来源文件与显式虚构演练台账：data/demo/dispatch-spacenet8，20道路/82建筑/3车辆；同区域配准影像已准备。
- [x] 数据保真与拒绝覆盖2项新增测试通过；脚本总15项，Java38及SDK注册通过。实际target插件已更新“创建演练路网”按钮。
- [ ] MapGIS原生NetCls文件尚未生成：实际独立JVM建网在DLL初始化失败，证据已保存。分钟权、资源节点绑定及调度入口自动衔接尚未完成，不能把道路GeoJSON称作已建好的原生网络。


## 最新进展：2026-08-28 道路—调度—报告与扩充训练

- [x] 道路核查状态/证据、原生源要素到全部网络子边映射适配、阻断边集、资源分配界面与业务报告包已实现并编译。
- [x] 实际启动用 target/mapgis-floodguard-plugin.jar 已重新构建，安装 SDK 注册/启用探针通过；无需再次手动构建旧代码。
- [x] Java 核心38、SDK配置38、脚本13、AI8、HTTP跨进程1、训练8项通过；真实候选模型CUDA API推理通过。
- [x] 官方样本扩至18组，55个对象已下载/校验；3米UTM道路缓冲、有效数据掩膜、类别平衡BCE+Dice、256分辨率、40轮训练完成。
- [x] 同4张留出影像比较：旧/新受淹建筑IoU 0.0261/0.1202，受淹道路0/0.0490；权重及报告独立保存，未替换在线模型。
- [ ] 原生完整业务验收：当前普通会话独立SDK探针两次DLL初始化失败；官方授权桌面已成功的历史事实不变，不能推断授权失效。新版提供宿主内“原生栅格验收”入口。
- [ ] 实际NetCls网络、分钟权、资源节点/台账、道路核查证据尚未在此流程提供并联调；轻/重淹动态权、全域已有阻断未完成。
- [ ] 完整洪水范围、面积/人口/社区风险、核验专题地图和完整灾情终验报告仍未完成；已实现的是可追溯业务报告，不冒充完整成果。
- [ ] 模型精度仍很低，不达生产/参赛质量验收，18组同地区样本不是独立区域测试。

后续按 docs/DISPATCH_WORKFLOW.md 与 NEXT_TASK.md 继续。下方旧状态仅作历史记录。

更新时间：2026-08-27

本轮已跑通官方样本 GPU 烟测训练、checkpoint 保存/重载和 PyTorch API 推理；IoU=0，绝不代表可用精度。模型/像素结果与 GIS 业务验收分开记录。

## Environment
- [x] 环境检查脚本可运行
- [x] Python 环境可复现
- [x] Java 环境可复现
- [x] MapGIS SDK 状态明确

## Upstream
- [x] MapGIS-Desktop-Java 已克隆并锁定
- [x] SpaceNet8 已获取并锁定
- [ ] 上游许可证与依赖已审计

## AI
- [x] 官方 SpaceNet8 配对样本下载校验
- [x] 官方 SiamUnet 架构 GPU 烟测训练及重载
- [x] SpaceNet8 最小真实模型 API 推理（烟测权重）
- [ ] 模型精度验证及完整数据训练
- [x] FastAPI health
- [x] FastAPI inference
- [x] CLI predict
- [x] AI Service 自动测试

## MapGIS
- [x] 洪涝插件基于已安装 SDK 编译打包
- [ ] 上游完整 Desktop 工程构建（旧源码 JavaFX 兼容问题未完成）
- [x] 影像选择/进度/取消等待面板编译
- [ ] 洪涝插件加载
- [x] Java 调用 AI 服务
- [ ] AI 结果加载至 MapGIS

## Product
- [ ] 灾损与道路阻断分析
- [ ] 安全救援路线
- [ ] 资源调度与风险评价
- [ ] 自动灾情报告
- [ ] 一键 Demo 与 E2E
- [ ] 发布包

## 开发交付（不是参赛完成）
- [x] 真实模型识别记录HTML导出与内嵌预览（非完整GIS灾情报告）
- [x] 风险缺失指标/非法数值拒绝计算回归
- [x] 官方GPU模型跨进程Java/HTTP推理测试
- [x] 配置训练2轮及恢复第3轮、留出评估
- [x] 独立MapGIS应用XML/Ribbon入口生成与回归
- [x] AI一键启停及桌面授权失败后的安全清理
- [x] 开发包打包，明确标注NOT COMPETITION-READY

参赛级发布包与完整GIS E2E仍保持未完成。最新源码阶段提交见Git；可继续执行入口见NEXT_TASK.md。

> 只有实际运行验证后的项目才标记为完成。
# 2026-08-27 21:32 增量状态

用户已验证：管理员宿主授权通过，识别面板可用，AI推理、识别记录导出、图层条目生成。实际生成GeoTIFF坐标与参考一致；调色板模式无颜色表的渲染问题已定位。

新增源码：掩膜Gray显示、RGB识别叠加、灾前/灾后/结果切换、URL去重、MapGIS两期网格及输出网格复核。独立编译与测试通过；运行中桌面锁定旧插件，尚待管理员重启验证新显示。未完成真实GIS灾损/路网/调度闭环，不是参赛成品。详情见NEXT_TASK.md。
# 2026-08-27 21:46 增量

新增四类掩膜、合并掩膜、RGB叠加的MapGIS空间化结果集与JSON网格验证记录；不把文件验证当成显示/灾损验收。Java23项、脚本13项、SDK插件注册/启用检查通过。运行中桌面未加载新版；批量原生转换和灾损统计仍待验证。详见NEXT_TASK.md。
# 2026-08-28 12:48 增量

六份实际空间化输出网格核验一致，RGB可见；部分二值TIFF仍为palette，单波段颜色解释待解决。新增原生MapGIS矢量斑块导出和坐标/闭合检查，Java26项及脚本13项通过，原生执行待验证。斑块不等于建筑实体，完整灾损/路网业务未完成。详见NEXT_TASK.md。
# 2026-08-28 12:56 增量

新增实体暴露去重统计、逐实体核查HTML报告、MapGIS原生相交查询适配层，29项Java测试通过。GUI数据选择/CRS获取与原生查询执行尚未验收，不宣称灾损模块完成。用户要求统一整合后再测试，后续不逐轮要求重启。
# 2026-08-28 13:02 增量

实体核查界面已接入数据图层选择、实际空间参考读取、原生查询和报告；多资源容量分配计划及路线数据校验已实现。Java31项、脚本13项通过。原生查询/新界面未实际验收，路网和调度联动、完整报告、模型质量仍未完成。按用户要求不逐轮请求测试。

## 2026-09-12 人工审查冻结与训练对照

- [x] Germany 197/197 样本人工可见性审查完成：接受 116，拒绝 81，待复核 0。
- [x] 冻结 98 个训练样本和 18 个验证样本，逐文件哈希与审查证据校验通过。
- [x] 两组 GroupNorm 40 轮 CUDA 训练完成；最佳验证宏平均 IoU 分别为 0.07780 和 0.08188。
- [ ] 受淹道路 IoU 仍为 0，普通道路在采样实验中塌缩；两个候选均不可发布，未切换在线模型。

详见 `docs/GERMANY_REVIEWED_TRAINING_COMPARISON_20260912.md`。

## 2026-09-12 道路诊断与阈值校准

- [x] 冻结数据道路监督核对：train 普通道路92张/受淹道路28张，validation 16张/3张，标签未在512栅格化时消失。
- [x] GroupNorm采样模型使用Germany validation逐类校准阈值，验证macro IoU由0.08188升至0.13387。
- [ ] 校准结果与选择使用同一验证集，不是独立精度；候选仍不可发布且未部署。

两折折外阈值评价 macro IoU 为 0.11405，普通/受淹道路 IoU 为 0.15317/0.02468。结论仍受限于18张验证图及仅3张受淹道路图。
## 2026-09-12 Two-stage feasibility completed（当前状态）

- Stage1对象分割与Oracle-Gated Stage2均完成40epoch；结论为预声明CASE A，值得下一阶段单独研究Predicted Gate，但尚非生产功能。
- Stage1开发集校准IoU：Building 0.3155、Road 0.1995；相比old-sampler单阶段union的0.2855/0.1830有所提高。
- Oracle status开发集校准IoU/AP：Building 0.3364/0.2896；Road 0.3626/0.5049。0.5下Road仍为0，说明校准重要。
- single_stage_tuning_status=paused；C/D及germany-reviewed-v1未覆盖。blind_holdout_used=false；Louisiana_used=false；production_ready=false；在线模型未修改。
- 完整报告：docs/TWO_STAGE_FEASIBILITY.md。训练已停止，无运行中模型实验。
## 2026-09-12 Predicted-Gate integration completed（当前状态）

- 冻结Stage1/Oracle Stage2完成Hard与Soft Gate端到端评价；无新训练。结论PG-B，未晋级two-stage predicted-gate candidate，继续保留germany-reviewed-v1 baseline candidate。
- Gate recall：Building 0.632、Road 0.398、Flooded Building 0.559、Flooded Road 0.440。Flooded Road错误中56.0%为Stage1 gate miss，8.2%为gate内Stage2 status错误。
- Hard/Soft四类macro IoU为0.099/0.142；Flooded Road IoU为0.097/0.087，均未满足预锁定晋级规则。Oracle Road IoU保留率仅26.9%/24.0%。
- recommended_integration=hard（仅代表若继续研究时的可解释集成方式，不代表晋级）；最多值得一次只改Stage1的专项研究，Stage2保持冻结。
- Two-stage feasibility=completed；Predicted-Gate integration=completed；production_ready=false；blind_holdout_used=false；Louisiana_used=false；在线模型未修改。
## 2026-09-12 Stage1 Road Gate Bottleneck Study completed（当前状态）

- 真实pipeline为整幅1300×1300直接缩放到512×512，不是native crop。道路骨架宽度中位数13→5 px，但512下≤4 px仅0.82%，没有普遍坍缩到1–2 px。
- 27个Road组件中24个中位宽5 px、3个7 px；5 px组pixel recall 0.408，7 px组0.348，未观察到“越细越漏”。Flooded Road gate recall 0.440，略高于普通Road约0.387。
- 低且跨图高度波动的Stage1 confidence/coverage是主要观测问题；边缘、NoData、黑边与width均没有证据成为主要原因。
- resolution_hypothesis_supported=false；未运行Stage1-E；model_research_phase_paused=true。Road/Flooded Road gate recall仍为0.398/0.440，Predicted-Gate Flooded Road IoU仍为0.097，PG门槛未达到。
- production_ready=false；blind_holdout_used=false；Louisiana_used=false；germany-reviewed-v1继续作为development baseline。
