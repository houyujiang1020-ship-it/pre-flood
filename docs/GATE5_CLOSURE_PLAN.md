# Gate 5 Closure Plan

## 已固定的执行契约

1. 只运行 `GROUND_TRUTH_VALIDATION`，输入由 `data/acceptance/gate5-v1/manifest.json` 锁定并逐文件校验 SHA-256。
2. 在 `EPSG:32632` 上计算实体建筑面积和道路线长度；官方 `flooded` 属性作为对象级期望值。
3. 固定按实体 ID 排序抽取 20 个建筑与全部 20 条道路，写入 `entity-validation.json`。Python 结果只是参考计算；只有 MapGIS 原生查询和 GUI 显示证据能完成现场核验。
4. 输出 `damage_analysis.json`、`damage_analysis.html` 和 `entity-validation.json`。缺失输入、CRS 异常、哈希异常、查询失败都必须失败关闭；查询失败不能变成零命中。
5. GUI 中必须明确显示 `GROUND_TRUTH_VALIDATION`，并将真值图层命名/样式与 `AI_PREDICTION` 区分；证据需包含真实 run_id、截图、日志和输出文件。

## 当前可完成项

- 82 个建筑与 20 条道路的实体级统计。
- 76 个受淹建筑、14 条受淹道路的对象级统计。
- 投影后的建筑占地面积和道路线长度。
- 两类各 20 条的稳定参考抽样、HTML 和 JSON 输出、失败关闭校验与回归测试。

## 阻断项和 PASS 条件

当前缺少固定区域的真实社区边界、人口数据和实际 MapGIS GUI 证据，因此 Gate 5 必须保持 `BLOCKED`，赛事 readiness 保持 4/9。补齐数据时必须记录发布者、原始 URL、许可、数据日期、CRS、范围和 SHA-256；随后计算社区/人口交叠、补齐五项风险指标，并在授权 MapGIS 宿主中完成原生查询与可视化。

只有校验器无错误、风险结果完整、两类抽样均不少于 20、MapGIS GUI 证据真实存在，且所有 blocker 清零后，才能把 `damage_analysis_completed` 改为 `true`。本计划不改变 Gate 6/7、模型或 production readiness。
