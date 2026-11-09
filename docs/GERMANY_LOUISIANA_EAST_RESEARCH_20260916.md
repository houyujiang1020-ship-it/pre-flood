# Germany + Louisiana-East 隔离训练结果

日期：2026-09-16。用户要求先训练新模型；独立 test 数据尚未下载。该实验为 `research_only`，没有改变旧基线、服务 checkpoint、阈值或 `production_ready=false`。

## 数据与运行边界

- 训练：德国已冻结人工审查 train 98 组 + Louisiana-East 官方公开训练集 599 组，共 697 组。德国 18 组原验证集保持不变；`test=[]`，报告中 `test=null`。
- Louisiana 的 599 组均有官方配对 CSV、灾前/灾后影像和 GeoJSON 标签；本轮逐文件核对了先前完整审计的字节数及 SHA-256。四类有正像素的 Louisiana 瓦片数依次为 389/88/522/127。未声称已对 Louisiana 做新的逐张可见性人工审查。
- Germany 原冻结 split SHA-256：`14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1`；新 train/validation/test split SHA-256：`90302621e46680801fd2a1da1aa07afaaae567c71ec1ecd8a05b033eb2017229`。
- 新配置：`config/training.germany-louisiana-east-research-20260916.json`；数据/来源清单：`experiments/datasets/germany-louisiana-east-research-20260916/manifest.json`。缓存使用对原审计缓存的硬链接，不重新标注或替换源文件。
- SiamUnet_diff + GroupNorm8，512 像素，30 epoch；正类感知采样 400 次/epoch，采样可重复，唯一瓦片数每轮少于 400。只用采样，不同时加正类像素权重。按德国验证四类 macro IoU 选 checkpoint，固定四类阈值均为 0.5。test 未参与任何计算。

## 结果

30 epoch 正常完成；最佳为 epoch 25。独立进程重载 `best_model.pth`，在德国原 18 组验证集复算得到相同 IoU。最佳 checkpoint SHA-256：`4b616d268973623001199aec3c53ce28225177a67e618eea7eedaa815f8b657f`。

| 同一德国验证集、固定 0.5 阈值 | 未淹建筑 | 受淹建筑 | 未淹道路 | 受淹道路 | macro |
| --- | ---: | ---: | ---: | ---: | ---: |
| 旧 Germany-only sampler | 0.22618 | 0.10007 | 0.00128 | 0.00000 | 0.08188 |
| 新 Germany + Louisiana-East | 0.12824 | 0.05272 | 0.22751 | 0.08152 | 0.12250 |

新模型在这一开发验证口径下改善道路，但两类建筑明显退步，不能称为四类全面提升。旧模型同一验证集重新调阈值得到的 0.13387 与上表固定 0.5 口径不同，不用于同表直接比较。没有为新模型调阈值，也没有独立区域 test；不得把 0.12250 当生产或比赛精度。

## 决定与下一步

- `promotion=rejected_pending_independent_test`：保留 checkpoint 供研究比较，不替换旧 development baseline，不加载到线上服务，不声称 production ready。
- Louisiana-East 在历史项目中曾作为研究 evaluation；现在进入训练后，历史 Louisiana 指标对这个新模型完全失去独立测试意义。
- 用户的另一个 test 集下载后，先核查来源、许可、标签语义、配对和与 Germany/Louisiana-East 的影像/地理范围重叠；冻结名单和文件哈希后，只运行一次事先约定的评估。无标签的公开测试影像不能计算 IoU。
- 如继续改进，应预声明建筑保留门槛与道路增益门槛，并优先调查跨地区采样比例/域差异；新实验不得用未来 test 选模或调阈值。

验证：`app/training/test_training.py` 14 项通过；最佳 checkpoint 重载后 18 张德国验证结果与 `history.json` 一致。训练配置及模型产物均在独立目录。
