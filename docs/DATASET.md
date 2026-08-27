# SpaceNet8 数据

来源：[SpaceNet8 官方页面](https://spacenet.ai/sn8-challenge/)，公共 S3 `spacenet-dataset/spacenet/SN8_floods/`。数据许可 CC-BY-SA-4.0，代码许可单独记录。

2026-08-27 下载 Germany_Training_Public 映射表及前两组配对影像和 GeoJSON 标注，共 7 个对象。URL、字节数、本地 SHA256 记录在 `data/spacenet8/sample-manifest.json`；该 hash 是本地完整性记录，不是官方签名。

第一组 0_41_59，第二组 0_45_64。灾前 RGB 为1300×1300；灾后分别786×786、785×786，EPSG:4326。须按地理参考配准，不能简单拉伸尺寸。目录 `data/spacenet8/sample/Germany_Training_Public/{PRE-event,POST-event,annotations}`，配对由 CSV 定义；标注包含 building/highway 与 flooded，未知 flooded 不能当作未受淹。

```powershell
.\scripts\download_data.ps1 -Mode sample -Count 2
.\scripts\download_data.ps1 -Mode full
```

sample 可增加 Count。full 下载 Germany_Training_Public、Louisiana-East_Training_Public、Louisiana-West_Test_Public 三份官方 tar.gz 至 archives，**目前不自动解压，也未实测全部下载**。脚本检查磁盘空间、支持 .part 续传、校验长度；大文件不进 Git。

Germany/Louisiana-East 是训练区域，Louisiana-West 是测试区域。烟测使用首组训练、第二组验证；两组不能代表可靠精度。完整训练需独立空间验证划分，不得用测试区选最优模型。无公开测试标签时不能声称测试精度。

原 data/demo PNG 为合成通信夹具，不是官方样例。
