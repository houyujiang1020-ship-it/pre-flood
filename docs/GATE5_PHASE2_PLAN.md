# Gate 5 Closure Phase 2 Plan

日期：2026-09-12。Phase 1 的建筑、道路、投影面积和长度计算保持冻结，不重新实现。Phase 2 只处理 community、population 和 MapGIS GUI evidence。

## AOI

固定范围为 SpaceNet8 Germany `0_41_59`，WGS84 中心点 `(7.0417978900, 50.5286460777)`，EPSG:32632 中心点 `(361211.403, 5599241.815)`。通过 BKG 官方 VG250-EW WFS 的真实空间查询确认，AOI 位于唯一 Gemeinde `Dernau`（AGS `07131017`）；不是依据 EPSG 或地名猜测。完整坐标见 `data/acceptance/gate5-v1/aoi.json`。

## 数据路径

1. Community：采用 BKG `VG250-EW` Gemeinde 面，数据时点 2024-12-31，许可 `dl-de/by-2-0`。保留原始 WFS 响应、请求 URL、SHA-256 和来源说明。
2. Population：优先采用 Destatis Zensus 2022 官方 100 m 人口格网，按真实格网与 AOI/受灾实体空间关系汇总；若格网获取或字段验证失败，人口继续 BLOCKED，不退化为拍定数字。
3. 配置：人口方法、公式、假设与局限写入 `config/gate5_population_method.yaml` 并记录配置哈希。
4. MapGIS：构建 Java 21 SDK 插件和 build manifest，准备明确的 `GT VALIDATION` 模式、固定人工截图清单和 GUI evidence manifest。正式图层相交、归属、专题表达仍必须由授权 MapGIS 宿主运行。

## 验收约束

- 一条跨社区道路的全局实体数只计一次；每社区长度按实际相交线段统计。
- 缺 community/population 不是零；查询失败也不是零。
- `continuous_flood_area` 与 `blocked_road_count` 保持 `null`，除非获得对应独立真值。
- validator 判据不降低。只有数据、风险、报告、抽样和真实 GUI 证据全部齐全才允许 PASS；否则 readiness 保持 4/9。
