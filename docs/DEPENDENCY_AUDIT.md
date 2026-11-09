# 依赖审计

## 最终 AI Service

| 依赖 | 用途 | GIS 核心能力 |
|---|---|---|
| FastAPI / Uvicorn / Pydantic | HTTP API、服务和数据校验 | 否 |
| NumPy | 影像数组计算 | 否 |
| Pillow | 普通图像读写 | 否 |
| PyYAML | 配置读取 | 否 |
| HTTPX / pytest | 测试 | 否 |

AI Service 当前不依赖 GDAL、Rasterio、GeoPandas、Fiona、Shapely 或 pyproj。

## SpaceNet8 隔离研究环境

官方 baseline 历史依赖包含 pygdal、Fiona、Shapely、GeoPandas、OSMnx 等，仅用于原始数据预处理、科研训练和赛题后处理研究，不进入最终参赛应用运行环境。

2026-08-27 实际建立 `.venv-training`，其中 Rasterio1.4.3 仅用于官方样本配准及标签栅格化；NumPy1.26.4/Pillow11.3.0/PyTorch2.5.1+cu121 用于科研烟测。依赖与 `.venv` 最终服务隔离。PyTorch 自身依赖 networkx，用于其内部功能，不用于最终应用路网分析。

## GIS 核心声明

目标要求：MapGIS 是唯一 GIS 应用开发核心，负责地图显示、空间数据管理、空间查询、叠加、缓冲、路网分析、专题制图和 GIS 可视化。AI 模块只输出遥感影像感知结果。

当前状态不等于目标已验收：SDK 加载代码及面板已编译，宿主授权验证未成功；空间统计、网络分析尚未实测。自写 EmergencyRouter 仅为业务测试实现，不能替代参赛所需 MapGIS 路网分析。
# 2026-08-28 训练隔离更新

仅 `.venv-training` 新增 Shapely 2.1.2 / pyproj 3.7.1，用于 SpaceNet8 科研标签的 3 米 UTM 道路缓冲（参照锁定上游 create_masks.py）。没有安装到 `.venv`，没有引入 Java 桌面或在线 AI GIS 链。最终道路映射、障碍路由仍由 MapGIS SDK 执行。
