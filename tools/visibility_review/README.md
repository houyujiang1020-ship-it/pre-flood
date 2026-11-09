# Germany 数据快速人工可见性审查工具

独立研究数据治理工具。读取现有 Germany train/validation 197 项 manifest，保留旧20项有效审查；帮助完成剩余177项。自动指标只排序，所有最终决定由人作出。本目录不被 AI 服务或 MapGIS 插件导入。

## 启动、停止与恢复

```powershell
Set-Location -LiteralPath 'C:\Users\33076\Desktop\高级开发'
.\scripts\start_visibility_review.ps1 -OpenBrowser
# 默认 http://127.0.0.1:18766；占用时顺延，具体地址见启动输出
.\scripts\stop_visibility_review.ps1
```

使用已有 `.venv-training\Scripts\python.exe` Python3.10。需要研究环境已有 numpy、rasterio、Pillow，以及本目录 requirements.txt 中的 FastAPI/Uvicorn/httpx；不向正式AI环境安装GIS依赖。依赖缺失时：

```powershell
.\.venv-training\Scripts\python.exe -m pip install -r tools\visibility_review\requirements.txt
```

只绑定127.0.0.1，禁止外网监听。启动核查真实映射表、全部源影像SHA256、文件及缓存，然后服务启动。初次缓存生成需数分钟，此后复用。`-SkipWarm` 可跳过全量预热，当前样本首次访问时仍按需缓存。`-Port 18776` 可指定首选端口。不会关闭其他Python进程。服务目录锁、PID、创建时间、解释器路径和启动随机标识用于防重复/防误停。

关闭或刷新后重开，自动定位首个pending；没有pending则定位首个needs_review；全部完成显示Review Complete。无须Save All。`回到待审`也遵循此规则。

## 界面与操作

顶部显示已非pending数/总数、accepted/rejected/needs_review/pending和已接受post1/post2数。Needs Review仍属未完成。PRE、POST1、POST2严格由官方列名映射，不依赖列表下标；缺POST2显示unavailable并禁用选择。

| 快捷键 | 功能 |
|---|---|
| 1 | accepted + post1 |
| 2 | accepted + post2（必须可用） |
| R | rejected，必须已有理由 |
| U | needs_review |
| N / P | 下一/上一筛选结果 |
| O | 切换标签叠加 |

在文本框、备注、选择控件内输入时不触发快捷键。每次决定立即写日志、flush/fsync后更新快照，再跳转下一pending（无pending则needs_review）。备注输入停顿450ms自动保存，导航前也保存；未保存时关闭页面会提示。遇到保存错误停留当前页并显示原因，不自动跳过。多标签页旧revision保存返回冲突，刷新重新审查。

点击图片弹出大图（仍为预览分辨率），支持浏览器缩放和弹窗滚动。Show Building为青色、Show Road为黄色，Show Flood Labels高亮受淹建筑粉色及受淹道路橙色；透明度150/255。未受淹标签为基础颜色。展开下方元数据可看文件名、原始尺寸、CRS、六项transform、SHA256及自动指标。

## Preview 生成策略和边界

缓存在 `experiments\diagnostics\visibility\germany-20260912-v2\previews\<sample_id>\<pre|post1|post2>\`。长边最多1024像素、保持原始宽高比、双线性下采样；RGB取源band1/2/3，统一clip到0..255后转uint8，与已有prepare_visibility_review.py范围一致。**不做逐图百分位拉伸、直方图均衡或自动对比增强**。逐图读取、顺序生成，避免将全部全分辨率数据读入内存。

每个metadata.json关联源路径、manifest SHA256、源预期SHA256、文件size/mtime、标签SHA256、尺寸/CRS/transform及策略版本；只有关联一致且全部产物存在才复用。原始影像/标签不写入、不删除；PNG仅用于审查，绝不能反向进入训练。

各图保留自己的栅格网格。标签按GeoJSON声明CRS（无声明采用WGS84）分别投影到每张图的预览transform，禁止仅按图片尺寸伸缩标签。建筑采用原多边形，道路采用原中心线，all_touched=True作显示栅格化；**不执行训练用3米道路缓冲**，所以这不是训练掩膜。flooded的yes/1/true为受淹，null按已有官方逻辑视为未受淹。不修改标签。可观察标签与地物错位，但同网格不证明真实地物已配准。缓存错误会单样本显示Sample Load Error并写日志，可记录needs_review。

## 状态、字段与问题原因

- accepted：图像可供后续数据治理使用，必须明确post1或post2；不等于模型/标签自动质量验收。
- rejected：图像质量不适用，selected_post必须null，至少一项flag或非空备注理由。
- needs_review：结论未定，可暂不指定post；仍阻止review_complete。
- pending：未完成决定，selected_post为null；可含已持久化的草稿备注。

| Flag | 含义 |
|---|---|
| CLOUD | 云遮挡影响目标可见性 |
| BLACK_BORDER | 明显黑边 |
| NO_DATA | 缺失有效像元 |
| INVALID_AREA | 大片无效区域 |
| TEMPORAL_MISMATCH | 时相不匹配 |
| ALIGNMENT_ERROR | 影像/标签空间错位 |
| LABEL_ERROR | 标签明显错误 |
| CORRUPTED_IMAGE | 损坏、无法读取 |
| OTHER | 其他，请填备注 |

没有flooded road/building或正类太少不是默认拒绝条件。自动可见性评分、近白比例、valid比例、亮度和梯度仅辅助排序，不代表云检测真值。Risk优先按较大风险降序排列，post建议显示较低风险排序，不自动点击接受。

记录包含sample_id、decision、selected_post、flags、reject_reasons、notes、reviewer、reviewed_at、source.pre/post1/post2及已有SHA256、review_tool_version、revision。sample_id为Germany_加原label文件stem；split+label保留兼容关系。旧20条的reason、reviewer、时间、evidence和原始record保留；旧自由文本理由不自动转换成flags。

## 保存、历史与备份

默认目录：`experiments\diagnostics\visibility\germany-20260912-v2\`。

- 原visibility_manifest.json、top20_visual_review.json、review_status.json和review_queue_top20.png只读，不重写。
- reviews.jsonl：新操作只追加，一操作一条，单调sequence，包含manifest/旧review哈希；落盘后才更新视图。第二次修改不删除第一次。
- review_state.json：旧审查兼容结果+新日志重放得到的全量状态，临时文件flush/fsync后os.replace。
- summary.json：随状态写入实时更新。只有pending=0且needs_review=0才review_complete=true。
- backups：每20次操作保留快照，最多10份，只轮换本工具的派生备份。主操作日志不限历史长度。
- review_integrity_report.json：清单数量/重复ID、缺文件、完整SHA256比对、未知审查引用、非法决定等。
- snapshot_recovery_report.json：快照损坏或比日志落后时明确报告恢复；日志和旧审查为真源。
- journal_integrity_error.json：日志损坏时停止写入并保留原件，不悄悄截断或猜测修复。应依据备份及原日志人工核对，勿覆盖/删除原审查证据。
- logs\visibility-review.log：服务启动、缓存、错误日志；每次启动另有对应实例stdout/stderr日志。

不要单独编辑review_state.json，它是派生快照。重新审查用All/Accepted/Rejected/Needs Review/Post1/Post2筛选或sample_id搜索，重新作决定即可，历史保留。要重置未审使用Pending按钮，同样记录操作日志。

## 汇总、完整性和报告

```powershell
.\scripts\summarize_visibility_review.ps1
.\.venv-training\Scripts\python.exe -m tools.visibility_review.cli check
```

报告输出 `docs\VISIBILITY_REVIEW_REPORT.md`，包含总数、状态、选择post分布、拒绝原因、flags、时间及manifest/review_state哈希。未完成明确INCOMPLETE。工具没有设置training_split_frozen=true、改train/val配置或启动训练的代码。审查完成后仍需单独的数据冻结程序。

## 测试（不改正式审查）

```powershell
.\.venv-training\Scripts\python.exe -m unittest tools.visibility_review.test_review -v
.\scripts\start_visibility_review.ps1 -Port 18776 -StorePath "$PWD\runtime\visibility-review-sandbox"
.\scripts\stop_visibility_review.ps1 -StorePath "$PWD\runtime\visibility-review-sandbox"
```

自动测试使用中文临时目录和小GeoTIFF fixture；真实197/旧20兼容测试仅在临时库中执行。浏览器冒烟用真实影像、独立sandbox库，页面顶端显示SANDBOX；不会写正式决定。缓存为可共享只读显示产物，sandbox决定与正式库完全隔离。
