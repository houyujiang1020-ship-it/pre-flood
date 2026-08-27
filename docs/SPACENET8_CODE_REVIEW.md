# SpaceNet8 代码审查

锁定源码见 UPSTREAM_LOCK.md；不修改 upstream。

- baseline/README.md：原始 Docker/NVIDIA 环境、训练和后处理命令。
- data_prep/geojson_prep.py：标注清洗、道路属性和速度准备。
- data_prep/create_masks.py：建筑、道路、速度、四通道洪水标签。
- data_prep/generate_train_val_test_csvs.py：训练验证划分。
- train_foundation_features.py、train_flood.py：要素和洪水训练。
- foundation_eval.py、flood_eval.py：推理、GeoTIFF/可视化输出。
- models/other/siamunetdif.py：SiamUnet_diff，灾前/灾后各3通道张量，输出 logits；烟测直接加载此文件。
- postprocessing：道路骨架/图、建筑矢量后处理为研究链，不移植为最终 GIS 核心。

四通道为非受淹建筑、受淹建筑、非受淹道路、受淹道路。烟测仅复用独立 Siamese 架构，并非官方完整双模型 baseline 复现。仓库未附可直接使用的 baseline best_model.pth，因此实际训练小样本并重载验证。

本项目 Windows 适配选 PyTorch2.5.1 CUDA12.1，不是上游原始版本。Rasterio 配准和标签栅格化隔离在 .venv-training。烟测 all_touched 道路线标签尚未等价复现官方道路缓冲预处理，不能用其指标宣传模型性能。最终 GIS 必须使用 MapGIS。
