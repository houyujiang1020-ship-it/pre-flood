# Gate 5 Data Inventory

盘点日期：2026-09-12。目标模式固定为 `GROUND_TRUTH_VALIDATION`；`AI_PREDICTION` 不参与本次 Gate 5 判定。

## 固定验收范围

采用 SpaceNet8 `Germany_Training_Public` 的 `0_41_59`。范围为 CRS84 `[7.0393649528, 50.5262131404, 7.0442308272, 50.5310790149]`。该瓦片包含 82 个建筑对象和 20 个道路对象，足以进行两类各 20 条的固定抽样。原始灾前、灾后影像网格不同，因此只能依赖地理参考配准，不能按像素尺寸直接拉伸。

冻结副本和逐文件 SHA-256 位于 `data/acceptance/gate5-v1/manifest.json`。来源为 SpaceNet8 官方挑战数据，许可为 CC BY-SA 4.0；本地数据及映射表未提供影像采集日期，manifest 将日期明确记为未知。

## 输入结论

| 输入 | 状态 | 证据与限制 |
|---|---|---|
| 建筑 | 可用 | 官方 GeoJSON，82 个面对象，稳定 OSM `id` |
| 道路 | 可用 | 官方 GeoJSON，20 个线对象，稳定 OSM `id` |
| 洪涝真值 | 部分可用 | 仅对象级 `flooded=yes/null`；76 个受淹建筑、14 条受淹道路 |
| 连续洪水范围 | 不存在 | 不能从对象标签构造或声称全域洪水面/面积 |
| 社区边界 | 缺失 | 仓库中无该固定范围的真实或赛事认可数据 |
| 人口 | 缺失 | 仓库中无该固定范围的真实、带许可与日期的数据 |
| 道路封闭 | 缺失 | `flooded=yes` 不等于已核实封路 |

`data/demo/dispatch-spacenet8*` 中的资源和 scenario 明确是演练夹具，不能作为真实社区、人口或资源台账。`data/external/osm-louisiana-east` 属于 Louisiana，既不匹配范围，也受本轮禁止读取/使用约束。

## 计量口径

实体按 `dataset + feature id + kind` 去重。建筑面积和道路长度由 CRS84 几何投影到 `EPSG:32632` 后计算。允许报告“受淹建筑占地面积”和“受淹道路长度”；连续洪水面积、封闭道路数、受影响社区和人口必须为 `N/A`/`BLOCKED`，不能写成 0。

现有 `RiskCalculator` 需要 flood、population、buildingDamage、roadAccessibility、medicalAccessibility 五个完整的 0–1 指标，默认权重为 0.30/0.25/0.20/0.15/0.10。缺人口、社区、连续洪水范围、道路可达性及医疗可达性时，风险评分必须拒绝计算。
