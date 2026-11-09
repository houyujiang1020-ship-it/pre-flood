# AI Pipeline Diagnostic Sprint — 2026-08-30

## 结论

本轮完成2/4/8固定patch记忆实验、归一化干预、历史模型对照、40组空间/缓存复核、796组类别统计、8组分辨率实验和正类采样审计。没有开始第三轮完整训练、没有下载已有801组数据、没有替换在线模型。

**不是“模型完全学不会”，也没有证据支持当前缓存配错瓦片或512导致道路标签大量消失。最明确的因果管线问题是共享BatchNorm训练/推理统计不一致；此外已证实少数类稀疏、可见性未纳入监督质量控制。历史完整模型本身仍存在拟合/泛化不足，不能声称只修BN即可解决其低精度。**

重要反证：对历史完整模型的德国train/validation各8张固定抽样，单改BN统计未提高指标。故不能量化“低精度有多少由BN/云/类别失衡造成”，也不能把本轮小样本98%记忆指标宣传成独立区域精度。正式训练放行条件尚未全部满足，competition readiness仍4/9。

## 1. 强制过拟合实验

- 真实训练集153瓦片中，按每类有效像素最小值选取8个不同源瓦片的128×128固定crop，每个crop四类均至少16个正像素。crop来自已有512缓存，**不是原生分辨率tile实验**。
- 2/4/8为同一固定池的嵌套子集；源文件SHA256和crop位置见`experiments/diagnostics/overfit/fixed-20260830-v1/patch_manifest.json`。
- seed=20260830，无随机增强，固定整批batch=2/4/8；Adam .001，温和正类权重上限8，BCE+0.5 Dice；为验证记忆能力，诊断中关闭Dropout。原始40轮训练的Dropout仍为0.2，本轮未修改它。
- 事先定义**诊断**标准：四类训练样本上的eval IoU都≥0.90，连续3个25步检查点；该标准不属于生产验收阈值。
- 原架构BN最多2000步；同数据、seed和损失的GN对照仅将BN改为8组GroupNorm，不修改锁定上游文件。所有模型均diagnostic_only、production_ready=false。

| 固定patch数 | 原BN最佳eval macro IoU | 同权重仅encoder用batch统计 | 同权重全部BN用batch统计 | GN对照eval macro IoU | GN完成步数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | .672145 | .969354 | .981739 | .981726 | 150 |
| 4 | .587313 | .998140 | .997514 | .959279 | 150 |
| 8 | .899336 | .999738 | .999738 | .977670 | 200 |

GN三组均满足每类IoU≥.90。原BN三组均未满足每类门槛（8组macro接近.90并不表示每类通过）。原BN训练loss接近零而eval可能恶化；归一化干预使用同checkpoint、同输入、同标签、同0.5阈值，未重新训练，能够直接定位统计模式影响。encoder内同一个BN先处理pre再处理post：train使用两期各自batch统计，eval使用共享的混合EMA；decoder中训练分布也随之改变。禁止用`model.train()`直接作为生产修复，因为它依赖批次、可能启用Dropout/更新状态。

GN逐类IoU（未淹建筑、受淹建筑、未淹道路、受淹道路）：

| patch数 | NFB | FB | NFR | FR |
| --- | ---: | ---: | ---: | ---: |
| 2 | .977144 | .975091 | .994847 | .979822 |
| 4 | .956378 | .936876 | .978114 | .965748 |
| 8 | .972876 | .957839 | .991764 | .988203 |

所有history保存training loss和eval loss、逐类TP/FP/FN/TN、IoU/precision/recall/F1；最终保存PR阈值曲线、GT/预测/概率PNG、原始概率/GT/valid NPZ、best checkpoint及SHA256。GN重载在相同cuDNN模式下概率逐值一致；关闭TF32后单样本与批量预测最大差≤1.41e-6。开启TF32的不同batch卷积算法产生最高.00260差异，初次严格检查失败记录保留，不隐瞒或当作BN状态依赖。

证据：

- `experiments/diagnostics/overfit/fixed-20260830-v1/summary.json`
- `experiments/diagnostics/overfit/fixed-20260830-v1/normalization_control.json`
- `experiments/diagnostics/overfit/groupnorm-20260830-v1/summary.json`
- `experiments/diagnostics/overfit/groupnorm-20260830-v1/reload_verification.json`
- 两个目录内每组`history.json`、`report.json`、`pr_curve.json`、`sample-*.png`、`probabilities_gt_valid.npz`。

## 2. 历史完整模型反证

`diagnose_historical_bn.py`只读tempered best模型（epoch34），固定seed随机选德国train8、validation8，512网格、batch1、阈值0.5；不再次运行Louisiana、不更新权重/阈值。

| 历史模型抽样 | 正常eval macro IoU | encoder batch统计 | 全BN batch统计 |
| --- | ---: | ---: | ---: |
| Germany train8 | .088951 | .075052 | .080175 |
| Germany validation8 | .090341 | .079099 | .078914 |

历史模型在训练区抽样本身也差，所以不能仅归因于跨区域domain shift。单改推理BN未救回历史模型；强制记忆实验的因果结论不能直接外推为历史模型全部精度下降的解释。历史第40轮训练目标loss .630951；验证loss .070208是无正类权重/无Dice的不同目标，**不能直接比较这两个loss数值推断过拟合**。

证据：`experiments/diagnostics/reports/historical_bn_control.json`及历史`history.json`。今后应先在新的归一化研究分支做小规模train/validation对照，不能篡改旧权重或盲目延长旧训练。

## 3. 输出/标签/API/GIS语义（来自当前源码）

| 模型channel | 训练正类条件 | API输出键/PNG | 当前最终GIS语义 |
| --- | --- | --- | --- |
| 0 | building且flooded不在yes/1/True | non_flooded_building | 非受淹建筑像素掩膜/斑块，非建筑实体数量 |
| 1 | building且flooded在yes/1/True | flooded_building | 受淹建筑候选斑块，需原生相交查询得到BUILDING实体 |
| 2 | highway且非building、非受淹 | non_flooded_road | 非受淹道路3m缓冲监督掩膜，非道路实体数量 |
| 3 | highway且非building、受淹 | flooded_road | 受淹道路候选斑块，需原生查询得到ROAD实体；不自动等于封路 |
| 无独立channel | channel1与3的union | flood_mask | 受淹结构并集，**不是完整洪水范围** |

依据：`train_smoke.py`的`flooded_class/load_pair`，`train_full.py`的`CLASSES/masked_loss/evaluate`，锁定`siamunetdif.py`的实际return x11d，`torch_backend.py`的CLASSES/predict，`ExposureAssessment.java`。虽然模型成员中存在LogSoftmax，forward没有调用它；实际为4个原始logits、sigmoid、独立BCEWithLogits及可选Dice，不是CE/softmax。

- class ID为channel索引0..3，不存在一个独立背景输出channel；背景为四通道全0。
- null按锁定官方预处理归入未受淹，不是ignore。有效监督是pre band1 nodata mask和reprojected post dataset mask的交集；没有cloud/visibility ignore mask。
- 建筑与道路可交叠；同类不同淹没属性的道路buffer也可能交叠，现行多标签语义允许。官方先单通道栅格化再拆类的重叠行为不同，已记录而未悄悄改标签。
- 现行研究API硬阈值均0.5；tempered验证校准的0.6/.45/.3/.3并未自动应用到服务，后续candidate必须连同阈值及预处理身份发布。没有把校准评估冒充当前API输出精度。

## 4. 空间、类别、分辨率结论

- Germany20、Louisiana20原始网格全部不同；现行代码真实重投影，40组重算与缓存逐tensor一致。extent overlap均1；不等于地物级控制点残差为零。6张图已目视检查，未假造40组人工通过。
- 发现云/云影明显的post仍valid；尤其Louisiana1_6_100几乎全云。当前仅用post1，未筛选post2。这是明确质量风险，尚未统计全数据云量，不能编造影响百分比。
- Germany train背景像素95.96%；FB仅35/153 tile、FR49/153；FB/FR有效像素仅.419%/.477%。纯背景tile实际0，不把无受淹tile误叫纯背景。
- 配置化正类采样器已接入train_full可选路径，实际CPU抽样3个epoch FB87/80/89次、FR94/84/92次；每轮153次含重复，唯一覆盖83/88/79。提高少数类曝光以牺牲当轮覆盖为代价，不是额外数据/精度证据。推荐片段显式diagnostic_only，不可直接训练。
- 8组/38条道路的512栅格化无完整道路消失，面积保持99.923%–100.153%；原生像素recall95.54%–96.99%。不支持大量标签消失为主因；没有排除RGB细节损失/小建筑影响，也没有声称原生分辨率一定更好。

详细证据：`LABEL_ALIGNMENT_AUDIT.md`、`RESOLUTION_EXPERIMENT.md`、`experiments/diagnostics/reports/class_distribution.json/.csv`、`experiments/diagnostics/sampling/sampler_audit.json`。

## 5. 放行状态与下一步

| 前置项 | 本次判定 |
| --- | --- |
| 四类标签/损失/梯度可以记忆 | GN诊断三组通过，原BN不通过每类门槛 |
| 地理参考与缓存一致 | 40样本通过；不代表全部影像地物配准已通过 |
| 标签空间对应 | 6张目视基本对应，有云遮挡；尚无全部控制点验收 |
| 少数类采样 | 策略/测试/真实抽样报告完成，未正式训练 |
| 可见性质量协议 | 待建立train/validation云影筛选及post选择规则 |
| 新盲holdout | 不存在可宣称完全未见的当前Louisiana；禁止事后改名伪装盲测 |
| production | false，未放行 |

下一步：在训练/验证数据上先完成可见性审阅清单与配准控制点验证；将GN作为明确新模型/预处理版本集成（诊断实现不是当前production架构），验证train/eval及服务路径一致，再冻结空间split及污染披露、预先声明少量对照和正式验收标准。需要真正未用于模型选择的新holdout或赛事独立评价；不能把已反复比较的599张改名为盲测。不得从本报告直接启动第三轮40/80 epoch。

## 复现命令

从项目根目录执行，overfit输出目录必须是新目录，不覆盖本轮证据：

```powershell
.\.venv-training\Scripts\python.exe app\training\diagnose_overfit.py --output experiments\diagnostics\overfit\fixed-repeat
.\.venv-training\Scripts\python.exe app\training\diagnose_normalization.py --run experiments\diagnostics\overfit\fixed-repeat
.\.venv-training\Scripts\python.exe app\training\diagnose_overfit.py --output experiments\diagnostics\overfit\gn-repeat --normalization groupnorm --patches experiments\diagnostics\overfit\fixed-repeat\fixed_patches.pt
.\scripts\run_tests.ps1
```

本轮所有实验进程均结束；没有后台正式训练等待。诊断源码与运行参数快照保存在overfit目录。旧checkpoint resume受trainer源码签名保护；本轮增加采样器后旧resume将拒绝，不应绕过签名继续训练。
