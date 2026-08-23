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

## GIS 核心声明

MapGIS 是唯一 GIS 应用开发核心，负责地图显示、空间数据管理、空间查询、叠加、缓冲、路网分析、专题制图和 GIS 可视化。AI 模块只输出遥感影像感知结果。
