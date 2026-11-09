# 公开免费数据集筛选：建筑、道路与洪水状态

核查日期：2026-09-16。目标为本项目 SpaceNet 8 风格的灾前/灾后高分辨率影像与四类标签：未淹建筑、受淹建筑、未淹道路、受淹道路。下表只登记已找到原发布方或维护方入口的候选；“免费获取”不等于许可无条件，也不等于标签可直接合并。没有下载原始大包、没有训练、没有触碰现有冻结划分或 blind holdout。

| 优先级 | 数据集及原始入口 | 内容与本项目用途 | 许可/获取核查 | 限制 |
| --- | --- | --- | --- | --- |
| A | [SpaceNet 8](https://spacenet.ai/sn8-challenge/) | 灾前/灾后高分辨率卫星影像，建筑、道路及 flooded 属性；唯一已核实与当前四类任务和影像模式完全同源的首选 | 官方 AWS 公共数据，CC BY-SA 4.0；页面提供 Germany 与 Louisiana 公共包 | Germany 已用于开发；现有 Louisiana 研究评估已重复接触，不能重新称作盲测；新并入前须按区域/事件审计重叠 |
| B | [FloodNet Supervised](https://github.com/BinaLab/FloodNet-Supervised_v1.0) | 2,343 张 Hurricane Harvey 灾后 UAV RGB 图；明确含 flooded/non-flooded building 与 road 四类，可做辅助预训练或域迁移对照 | 原发布方给出下载入口；CDLA Permissive | 无配对灾前卫星影像；俯视角度/高度、地理区域和标签语义与 SN8 不同，不能无转换地拼入当前四类训练 |
| B | [SpaceNet 5 Roads](https://www.spacenet.ai/sn5-challenge/) | 高分辨率卫星道路网络标签；适合单独预训练 Stage 1 道路提取 | 官方 AWS 公共数据、CC BY-SA 4.0；页面称免费但下载可能需 AWS 账户 | 无 flooded 属性；原始道路中心线/速度标签须按项目既定缓冲和栅格规则转换；不可给道路赋受淹标签 |
| B | [SpaceNet 3 Roads](https://spacenet.ai/spacenet-roads-dataset/) | 道路提取预训练与外地区泛化对照 | 官方 AWS 公共数据、CC BY-SA 4.0 | 无洪水状态；部分地域/影像可能与其他 SpaceNet 数据重复，需按 AOI 审计 |
| C | [SpaceNet 2 Buildings](https://spacenet.ai/spacenet-buildings-dataset-v2/) | 建筑 footprint 预训练 | 官方 AWS 公共数据、CC BY-SA 4.0 | 无洪水状态；不针对当前道路瓶颈 |
| C | [xBD / xView2](https://xview2.org/dataset)；[官方基线说明](https://github.com/DIUx-xView/xView2_baseline) | 灾前/灾后卫星图和建筑损伤标签；可作灾害场景表征或建筑定位预训练 | 官方站点需浏览器 JavaScript/注册；CMU 称数据以 Creative Commons 公开，具体使用条款应以下载时原始许可为准 | 建筑损伤等级不等于受淹；没有四类道路标签；切勿把“受损”映射为“受淹” |
| C | [OpenEarthMap](https://github.com/bao18/open_earth_map) | 0.25–0.5 m 多地区土地覆盖标签，可作道路/建筑视觉表征或域泛化 | 免费公开；图像及标签许可随原始影像来源变化，部分为 CC BY-NC-SA 4.0，必须逐地区核查 | 不是灾前/灾后洪水数据；项目代码的 MIT 许可不代表全部图像为 MIT |
| D | [RescueNet](https://github.com/BinaLab/RescueNet-A-High-Resolution-Post-Disaster-UAV-Dataset-for-Semantic-Segmentation) | 灾后 UAV 场景、建筑损伤、road clear/blocked；可辅助研究道路可通行性定义 | 免费下载；原发布方标注 CC BY-NC-ND | road blocked 不等于 flooded road；非商业/禁止演绎限制，先核实加工训练是否符合条款；不建议直接并入四类训练 |
| D | [WorldFloods](https://spaceml-org.github.io/ml4floods/content/worldfloods_dataset.html) | Sentinel-2 洪水水面掩膜；可做独立洪水范围研究 | 公开获取，原项目注明 Creative Commons 非商业许可；约 300 GB | 中分辨率、仅水面，无建筑/道路 flooded 属性；不能代替 Gate 5 连续洪水面真值或四类标签 |
| D | [Sen1Floods11](https://github.com/cloudtostreet/Sen1Floods11) | Sentinel-1 SAR 洪水水面标签；可做不同模态的洪水研究 | 原发布方开放云存储下载；本次未在原仓库确认精确数据许可，采用前需复核 | SAR 与本项目 RGB 卫星输入不同；无四类实体标签 |

## 当前排序与落地边界

1. **最快的辅助数据实验**：优先审计 FloodNet 原始标签、下载包许可和样本质量；只做隔离的辅助预训练/域迁移对照，不改 Germany 冻结验证集。它提供目标四类，但缺灾前图，模型输入适配需明确设计。
2. **针对已观测瓶颈**：用 SpaceNet 5（可辅以 SpaceNet 3）预训练灾前道路 Stage 1；在同一 Germany 验证与既定晋级规则下比较道路召回、普通/受淹道路 IoU、其他两类退化和误报。此用途与项目 Road Gate recall 偏低的诊断相符，但收益尚未证明。
3. **扩充真正同任务训练样本**：优先取得更多经许可、具备清晰灾前/灾后配准和逐建筑/逐道路洪水状态的独立事件；目前核实的现成数据中，只有 SpaceNet 8 完全匹配。其他数据须保留各自语义，不得伪造 flooded 标签。
4. **防止评估污染**：按事件、AOI、影像 footprint 与时间去重。Germany 现有冻结划分不重写；Louisiana 已被用于研究评估，不作为全新 blind holdout。新样本只进入预先声明的训练/新验证方案，独立测试在实验结束前不得查看。
5. **引入前需记录**：原始 URL、下载时间、发布者、许可证原文、原包与单文件 SHA-256、GSD/CRS、标签定义、灾前/灾后匹配、与现有样本的空间重叠、建议用途。未知或冲突条款标记为待核查，不默认可商用或可再发布。

本目录是来源筛选，不是质量提升证明；未修改模型、阈值、训练集或 `production_ready=false` 状态。
