# 与本项目强相关的开源算法及适配路线（2026-09-26）

## 结论

可以借鉴，而且当前最有希望的方向不是把现有 `SiamUnet_diff` 简单替换成更大的网络，而是吸收 SpaceNet 8 优胜方案中被多支队伍独立采用的结构：先学习建筑/道路“在哪里”，再用灾前/灾后特征判断“是否受淹”，并给道路连通性和建筑边界增加辅助监督。建议在本项目内重新实现这些思想，保留现有数据审计、GroupNorm、域平衡采样、固定 0.5 阈值和独立测试门禁。

首选参考代码是官方 SpaceNet 8 仓库和第 5 名方案，许可证均为 Apache-2.0，任务定义和当前项目几乎完全一致。ChangeFormer、CoANet 等适合作为某个模块的研究参考，不适合整仓替换当前管线。

## 当前项目约束

- 输入：同一区域灾前、灾后高分辨率光学影像。
- 输出：未淹建筑、受淹建筑、未淹道路、受淹道路四通道。
- 已知问题：样本和地域分布不平衡；建筑与道路彼此竞争；受淹道路最不稳定；18 张 Germany 验证片已被反复用于研究选择，不能当作最终泛化精度。
- 当前硬件约束：RTX 4050 6 GB，不能照搬 35 模型、5 折、EfficientNet-B5/B6 的竞赛集成。
- 当前模型应继续保持 `research candidate`；另行下载的 test 必须冻结后只做一次最终评价，不能参与阈值或轮次选择。

2026-09-26 完成的域平衡对照已把相同 Germany 开发验证、固定 0.5 macro IoU 从普通合并训练的 0.12250 提高到 0.14390，但道路两类从 0.22751/0.08152 回落到 0.20941/0.05412。这进一步支持“先解耦目标定位与受淹状态、再增加道路连接监督”，而不是继续只调全局采样比例。

## 强相关开源项目

| 优先级 | 项目 | 与本项目的关系 | 可借鉴内容 | 适配判断 | 许可证/限制 |
|---|---|---|---|---|---|
| S | [SpaceNet 8 官方优胜方案与 baseline](https://github.com/SpaceNetChallenge/SpaceNet8) | 同一数据、同一灾前/灾后任务、同类四通道输出 | 前五名完整方案；Siamese HRNet+OCR；foundation/flood 分阶段；RMI、Focal+Dice、Lovasz；外部 SpaceNet/xBD 预训练；增强与后处理 | 作为主设计依据 | Apache-2.0 |
| S | [SpaceNet 8 第 5 名完整实现](https://github.com/motokimura/spacenet8_solution_5th-place) | 直接输出四类；公开训练、推理和预训练迁移细节 | 建筑 body/border/contact，道路 skeleton/junction；foundation 权重初始化 Siamese flood；EMA；空间 5 折；影像清洗；重叠裁块；SpaceNet 5/xView2 迁移 | 最适合拆成轻量模块移植 | Apache-2.0；原方案依赖大显存 Linux 和多模型集成，不能原样运行 |
| A | [SpaceNet 5 道路优胜方案](https://github.com/SpaceNetChallenge/SpaceNet_Optimized_Routing_Solutions) | 为当前薄弱的道路通道提供可迁移先验 | 道路预训练、骨架和路网优化；官方仓库含前五名方案 | 优先迁移 encoder/道路 head，不整仓迁移 | Apache-2.0 |
| A | [CRESI](https://github.com/avanetten/cresi) | 道路像素转可路由图，与项目应急调度目标直接相关 | 道路分割后骨架化、矢量化、图构建、速度/通行时间 | 用于下游拓扑和 APLS 验证；不能代替四类像素模型 | Apache-2.0 |
| A | [CoANet](https://github.com/mj129/CoANet) | 专门解决遥感道路断裂和连通性 | connectivity attention、八方向连接监督 | 先复现连接辅助 head 的思想；暂不复制 GPL 代码 | GPL-3.0，分发组合代码前需处理许可证兼容性 |
| B | [ChangeFormer](https://github.com/wgcban/ChangeFormer) | 灾前/灾后遥感变化检测 | Siamese Transformer、分层差分、多尺度解码、预训练 | 可做轻量 ChangeFormer/SegFormer-B0 对照；需改成四类语义而非二值变化 | MIT；完整 V6 对 6 GB 显存和小数据不经济 |
| B | [BIT-CD](https://github.com/justchenhao/BIT_CD) | 用 Transformer 表示双时相变化 | 轻量 token 化双时相交互 | 只借鉴结构思想，重新实现四类 head | 仓库未提供标准 LICENSE，README 限定学术非商业用途；不直接纳入产品代码 |
| B | [FADS-Fusion](https://github.com/vtnsi/FADS-Fusion) | 使用 SpaceNet 8 做受淹建筑/道路融合与不确定性 | Dempster-Shafer 决策级融合、折外可靠度、uncertainty map | 等两个独立强模型出现后再用；弱模型之间融合不会解决表征不足 | 仓库未发现标准 LICENSE，暂仅研究参考 |
| C | [Swin Transformer](https://github.com/microsoft/Swin-Transformer) | SpaceNet 8 第 3 名使用 Swin+UPerNet | 多尺度 Transformer encoder | 只考虑 Swin-T；Swin-B+UPerNet 在 6 GB/512 输入下成本过高 | MIT |

## 优胜方案中可验证的共同规律

1. **把基础目标和淹没状态解耦。** 官方第 2、4、5 名均先训练建筑/道路基础分割，再用其权重初始化或约束双时相洪涝模型。当前项目曾验证“硬 predicted gate”会漏掉真值，因此适配时使用可微的 soft gate 和膨胀后的目标先验，保留 flood branch 在 gate 外的小幅纠错能力。
2. **给细长/相邻目标增加辅助监督。** 第 5 名用建筑 body/border/contact 和道路 skeleton/junction 五个基础通道。该设计直接针对当前道路断裂、建筑粘连和像素占比过低的问题，比继续单独调 Dice/Tversky 更有针对性。
3. **迁移学习比从头训练更重要。** 第 5 名报告 SpaceNet 5 道路权重和 xView2 建筑权重均带来提升；第 2、3、4 名也使用 SpaceNet 2/3/5、Inria、Massachusetts、xBD 等外部预训练。当前 Germany+Louisiana 数据量仍小，先验价值很高。
4. **训练稳定性要单独处理。** 第 5 名指出 Siamese flood 验证指标轮间波动明显，并用 EMA 和较大的 7×7 末端卷积缓解。当前实验也出现明显轮间波动，EMA 是低成本、可单变量验证的改动。
5. **配准/影像质量影响很大。** 优胜方案会在多个 post 影像中按与 pre 的 MSE 选择更可靠的一张，排除黑图、云和明显错位；作者还建议用 LoFTR/SuperGlue 做更精确配准。本项目已有人工可见性审查，应在其基础上增加自动配准质量分数，不能只靠增强掩盖错位。
6. **验证必须按空间分组。** 第 5 名按地理相邻块做 5 折，避免邻近瓦片泄漏。本项目下一轮应至少建立 Germany/Louisiana 空间分组的 3 折开发评估；当前 18 张 Germany validation 只保留作连续性对照。

## 建议实现：FloodGuard-v2-lite

### 1. 轻量基础模型

- encoder 采用 ImageNet 预训练的 EfficientNet-B3 或 ResNet50；6 GB 显存下先用 B3。
- decoder 输出 5 个辅助通道：building body、building border、building contact、road skeleton、road junction。
- 训练使用 384×384 或 448×448 原分辨率随机裁块，不再把整张影像统一缩放后丢失细道路；推理用 25% 重叠滑窗并加权融合。
- 基础损失先保持 `BCE + Dice`，用辅助通道改善形状，不同时叠加强正类权重。

### 2. 轻量双时相洪涝模型

- pre/post 共享 foundation encoder；在每层融合 `pre`、`post`、`|pre-post|` 三类特征。
- 由 foundation checkpoint 初始化，输出现有四类通道，保证接口不变。
- 基础目标概率经过小幅膨胀后作为 soft gate：`p_class = p_foundation × p_status + epsilon × p_status`。`epsilon` 保留漏检纠错，避免此前硬 gate 的召回崩溃。
- decoder 末端采用 7×7 卷积；保存训练权重和 EMA 权重，统一以固定 0.5 阈值评估。

### 3. 数据与增强

- 延续当前每轮 Germany/Louisiana 1:1 域平衡，再在域内做类别感知采样。
- 增加成对几何增强，保证 pre/post/mask 同步；对两期影像分别施加有限的亮度、对比度、gamma、雾、噪声和运动模糊，以模拟观测差异。
- 自动记录 pre/post 配准位移、黑像素率、云/低对比度指标；高风险样本降权或进入人工复查，不静默删除。
- test 不进入任何训练、阈值搜索、EMA 选择或折分。

### 4. 评价

- 主指标：固定 0.5 的四类 IoU 和 macro IoU。
- 辅助指标：每类 precision/recall/F1、PR-AUC；道路增加 skeleton IoU、连通率和 APLS；建筑增加对象级 F1。
- 每个试验重载 `best_model.pth` 独立复算，报告均值和空间折间方差。
- 只有独立 test 到位且未被用于模型选择后，才可给出泛化精度和是否晋级 production 的结论。

## 按收益/成本排序的实验计划

| 顺序 | 单变量实验 | 保持不变 | 晋级条件 |
|---|---|---|---|
| E1 | 在当前最优训练方案上增加 EMA | 数据、采样、网络、损失、30 epoch | 固定 0.5 macro 提升，且至少 3/4 类不显著退化；重复种子后仍成立 |
| E2 | 384/448 原分辨率裁块 + 重叠推理 | 当前模型与损失 | 道路两类 IoU、召回和连通率改善，建筑不大幅下降 |
| E3 | foundation 五辅助通道 | E2 数据管线 | 建筑对象 F1、road skeleton IoU/连接率改善 |
| E4 | 用 E3 初始化 soft-gated Siamese flood | E3 foundation 固定 | 四类 macro、受淹道路和受淹建筑同时优于当前最佳 |
| E5 | SpaceNet 5 道路权重迁移 | E4 其余条件 | 空间折均值改善，不以单个 18 张验证集决定 |
| E6 | 轻量 ChangeFormer 或 CoANet 风格连接 head | E4/E5 最佳配置 | 只有 E1-E5 仍出现明确表征瓶颈时启动 |
| E7 | 两模型折外融合/不确定性图 | 至少已有两个互补强模型 | 独立开发折提升且校准误差下降 |

首轮不建议同时改变 backbone、裁块、loss、增强和采样；否则无法知道提升来自哪里。也不建议先做大模型集成、TTA 或同一验证集阈值搜索，这些会放大当前验证集过小和被反复查看的问题。

## 预期与风险

- 最现实的近期收益来自 E1 和 E2：改动小，能直接缓解当前的轮间波动和细道路缩放损失。
- 最大的结构性收益可能来自 E3/E4，但需要新标签派生、双阶段 checkpoint 初始化和推理融合，工程量更高。
- 外部预训练权重的标签定义、波段、GSD 和许可证必须逐项核对；“公开可下载”不等于能直接并入产品。
- 当前验证样本太少，任何 1～2 个百分点的变化都可能是样本/随机种子噪声。正式结论依赖空间折和未来冻结 test。

## 一手资料

- [SpaceNet 8 官方优胜方案与 baseline](https://github.com/SpaceNetChallenge/SpaceNet8)
- [SpaceNet 8 任务论文（CVPR EarthVision 2022）](https://openaccess.thecvf.com/content/CVPR2022W/EarthVision/papers/Hansch_SpaceNet_8_-_The_Detection_of_Flooded_Roads_and_Buildings_CVPRW_2022_paper.pdf)
- [SpaceNet 8 第 5 名完整方案](https://github.com/motokimura/spacenet8_solution_5th-place)
- [SpaceNet 5 官方优胜方案](https://github.com/SpaceNetChallenge/SpaceNet_Optimized_Routing_Solutions)
- [CRESI](https://github.com/avanetten/cresi)
- [CoANet](https://github.com/mj129/CoANet)
- [ChangeFormer](https://github.com/wgcban/ChangeFormer)
- [BIT-CD](https://github.com/justchenhao/BIT_CD)
- [FADS-Fusion](https://github.com/vtnsi/FADS-Fusion)
- [Swin Transformer](https://github.com/microsoft/Swin-Transformer)
