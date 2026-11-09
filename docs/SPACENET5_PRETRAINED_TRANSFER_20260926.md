# SpaceNet-5 XD_XD 预训练迁移审计（2026-09-26）

## 结论

SpaceNet-5 冠军 XD_XD 的 SE-ResNeXt-50 U-Net 权重已从官方公开 S3 下载、校验、转换并在当前 PyTorch/CUDA 环境严格加载。该权重可以作为后续道路专用全量微调的初始化来源，但不能直接作为本项目道路 gate，也不能靠冻结网络后只训练一个六通道输出头替换现有 foundation。

预注册的 head-only 可行性实验已停止：最佳建筑/道路对象 IoU 为 `0.012889 / 0.128205`，均值 `0.070547`；现有 E3c 为 `0.284363 / 0.295812`，均值 `0.290088`。候选低 `0.219541`，因此 `promotion=rejected`。E4 四类 research leader 不变。

## 来源与可复现权重

- 官方源：`https://spacenet-dataset.s3.amazonaws.com/spacenet-model-weights/spacenet-5/xd_xd/serx50_focal/fold0/fold0_best.pth`
- 原始旧式整模型：`models/pretrained/spacenet5-xdxd/serx50_focal/fold0/fold0_best.original.pth`
- 原始大小：`301620821` 字节
- 原始 SHA-256：`716c4fa33ce211517d0699b01537f49889c35bb5e15e692a84d8452ee6daa783`
- 转换后的纯 `state_dict`：`models/pretrained/spacenet5-xdxd/serx50_focal/fold0/fold0_best.state_dict.pth`
- 转换后 SHA-256：`f3201bb889bd8939d70a87c52ed4b5fb7a737bc8a83ea525416b89c37134b269`
- 架构来源：`upstream/SpaceNet8/05-motokimura/code/spacenet8_model/models/xdxd_sn5/senet.py`
- 许可：项目内 `upstream/SpaceNet8/05-motokimura/code/licenses/README.md` 将该 SpaceNet-5 模型与代码列为 Apache-2.0。

作者提供的转换版镜像 `https://motokimura-public-sn8.s3.amazonaws.com/xdxd_sn5_serx50_focal.zip` 当前匿名访问返回 S3 `AccessDenied`，因此本项目没有把它作为依赖。`scripts/fetch_public_file.py` 使用官方对象、Range 断点/并发下载、预期大小和 SHA-256 回执；`scripts/convert_xdxd_checkpoint.py` 只在原始 SHA 匹配后，将本地同源类映射到旧 pickle 模块名并导出纯张量。

## 兼容性和零样本探针

402 个权重张量、75,370,061 个参数严格加载，无 missing/unexpected key。512×512 CUDA 前向输出为 `1×8×512×512`，有限值，峰值分配约 522 MB。固定 0.5 在既有 Germany 18 张开发验证上的道路对象零样本结果为：

| IoU | precision | recall |
|---:|---:|---:|
| 0.012310 | 0.141481 | 0.013303 |

这是域差异诊断，不是独立精度。它证明原始概率不能直接用作 gate，也没有触碰 Louisiana-West。

## 预注册 head-only 实验

固定协议来自 `experiments/germany-louisiana-xdxd-sn5-head-foundation-20260926/preregistration.json`：

- train/validation/test 为 697/18/0，沿用已使用过的 Germany 开发验证；
- 10 epoch、固定 0.5、既有域平衡 sampler 和六通道 BCE+Dice；
- 编码器、解码器和 BatchNorm 统计全部冻结，只训练新的六通道 3×3 head，共 1,734 参数；
- 旧 SpaceNet-5 最后道路通道只初始化本项目 `road_body` 通道；其余 head 通道随机初始化；
- 只在均值超过 E3c 的 `0.29009` 时，才保留为未来新空间折的全量微调方向；本实验本身没有生产晋级资格。

最佳第 9 轮结果：

| 模型 | building IoU | road IoU | mean object IoU |
|---|---:|---:|---:|
| XD_XD frozen + local head | 0.012889 | 0.128205 | 0.070547 |
| E3c local single U-Net | 0.284363 | 0.295812 | 0.290088 |
| 差值（candidate - E3c） | -0.271474 | -0.167607 | -0.219541 |

独立进程重载复现相同 IoU。candidate checkpoint SHA-256 为 `7eb281b2970e191f92b3078fcd8bade06bb9e9d0db8ca041042bd1a7711e87e9`；封存决策为 `experiments/germany-louisiana-xdxd-sn5-head-foundation-20260926/evaluation.json`，SHA-256 为 `cbfafdd2a2fb906f030dcdd675d3b8418d246b495fb77e5b83e35d6a32ee479d`。

## 后续边界

不在 Germany validation 或已经揭示的 Louisiana 空间折继续解冻层数、调学习率、阈值或 epoch。若取得新的带四类真值区域，应在查看其结果前冻结地理折，再比较同架构随机初始化与 SpaceNet-5 全量微调；建筑分支需要建筑专用预训练或本地 E3c，不能期望道路权重经一个线性 head 恢复建筑。

