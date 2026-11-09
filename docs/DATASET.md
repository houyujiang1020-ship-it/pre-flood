# 训练数据下载与准备

本项目以 SpaceNet 8 的灾前和灾后卫星影像及建筑、道路洪水标签为主要训练数据。数据采用 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)，来源和区域划分见 [SpaceNet 8 官方挑战页](https://spacenet.ai/sn8-challenge/)。

| 区域 | 用途 | 官方下载 |
| --- | --- | --- |
| Germany | 有标注训练集 | [Germany_Training_Public.tar.gz](https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/tarballs/Germany_Training_Public.tar.gz) |
| Louisiana East | 有标注训练集 | [Louisiana-East_Training_Public.tar.gz](https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/tarballs/Louisiana-East_Training_Public.tar.gz) |
| Louisiana West | 官方测试集，公开包无标签 | [Louisiana-West_Test_Public.tar.gz](https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/tarballs/Louisiana-West_Test_Public.tar.gz) |

从浏览器手动下载时，可将训练归档放在 `data/spacenet8/archives/`。测试包单独保存，训练和调参时只使用有标注训练区的适当划分。FloodNet 等辅助研究数据的原始入口见 [数据来源目录](PUBLIC_FLOOD_DATASET_CATALOG_20260916.md)。

## 使用项目脚本下载

在 Windows PowerShell 中进入仓库根目录。首次运行先执行 `.\scripts\setup_python.ps1` 创建下载脚本使用的 Python 环境。

2026-08-27 下载 Germany_Training_Public 映射表及前两组配对影像和 GeoJSON 标注，共 7 个对象。URL、字节数、本地 SHA256 按 AOI 记录在 `data/spacenet8/sample-<AOI>-manifest.json`；兼容路径 `sample-manifest.json` 只保存德国清单。该 hash 是本地完整性记录，不是官方签名。

第一组 0_41_59，第二组 0_45_64。灾前 RGB 为1300×1300；灾后分别786×786、785×786，EPSG:4326。须按地理参考配准，不能简单拉伸尺寸。目录 `data/spacenet8/sample/Germany_Training_Public/{PRE-event,POST-event,annotations}`，配对由 CSV 定义；标注包含 building/highway 与 flooded，未知 flooded 不能当作未受淹。

```powershell
.\scripts\download_data.ps1 -Mode sample -Count 2
.\scripts\download_data.ps1 -Mode sample -Area Louisiana-East_Training_Public -Count 24
.\scripts\download_data.ps1 -Mode full -Workers 8
```

sample 可增加 Count。full 默认只下载 Germany_Training_Public 与 Louisiana-East_Training_Public 两份**有标注**训练包；可重复传入 `--area` 限定 AOI，不再误下无标签 Louisiana-West 测试包。2026-08-29 HEAD 实测两包分别为 1,357,293,885 与 3,336,023,039 字节。下载到 archives，暂不自动解压。脚本检查磁盘空间，使用 1--16 路 HTTP Range（默认 8 路），每段独立断点续传，合并前后校验长度；大文件不进 Git。已有单连接 `.part` 会作为完整前缀复用。不能把未完成下载写成已获得数据。

## 免费辅助数据筛选（2026-08-29）

优先级只按本项目四类输出与 SpaceNet8 传感器域的适配程度排列：

1. **FloodNet Track 1**：2,343 幅灾后高分辨率无人机影像，语义类别直接包含受淹/未受淹建筑与道路；CDLA-Permissive。官方 Dropbox 在本机网络超时，因此先记录来源，不将其伪装成已下载数据。它适合类别预训练，但与 SpaceNet8 卫星灾前/灾后配对仍有域差异。
2. **SpaceNet 2/3/5**：分别强化建筑和道路基础要素。SpaceNet8 官方获奖方案明确采用这些数据预训练，再在 SpaceNet8 上微调；许可按各数据集页面核验。
3. **Sen1Floods11**：约 14 GB，Sentinel-1/2、10 m、仅水体/非水体。可用于洪水范围辅助预训练，不可直接替代四类道路建筑监督。
4. **WorldFloods**：509 场洪灾，最新版本约 76 GB，CC-BY-NC-4.0；分辨率和任务不匹配且超过当前合理空间预算，暂不下载。

不采用只含水位传感器表格、洪水风险 DEM、VQA 文本或无明确许可的镜像来训练当前像素级四类模型。

Germany/Louisiana-East 是训练区域，Louisiana-West 是测试区域。烟测使用首组训练、第二组验证；两组不能代表可靠精度。完整训练需独立空间验证划分，不得用测试区选最优模型。无公开测试标签时不能声称测试精度。

原 data/demo PNG 为合成通信夹具，不是官方样例。
