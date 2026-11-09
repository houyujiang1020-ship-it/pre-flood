# Gate 5 Complete Damage Analysis Closure Record

日期：2026-09-12。结论：**BLOCKED；Gate 5 未通过，competition readiness 保持 4/9。**

## 已完成

- 固定验收数据集：`data/acceptance/gate5-v1/`，模式为 `GROUND_TRUTH_VALIDATION`，含灾前影像、灾后影像、官方对象标签、来源/许可/CRS/范围/哈希及语义清单。
- 实体参考分析：82 个建筑、20 条道路；76 个受淹建筑、14 条受淹道路。
- `EPSG:32632` 投影计量：建筑总占地 12,628.097 m²，受淹建筑占地 12,281.684 m²；道路总长 2,759.188 m，受淹道路长 2,446.522 m。
- 固定抽样：按实体 ID 稳定排序，建筑 20 条、道路 20 条，记录在 `runtime/acceptance/gate5-gt-20260912-01/entity-validation.json`。
- 运行产物：同目录下 `damage_analysis.json`、`damage_analysis.html` 和 `entity-validation.json`。
- 失败关闭校验：缺文件、错误模式、输入缺失/哈希异常、CRS 异常、对象不足、风险未完成、GUI 证据缺失及 blocker 未清均不能通过。查询/读取错误抛出失败，不会转成零影响。

## 统计含义

SpaceNet8 的 `flooded=yes` 是建筑或道路对象属性。本次只报告受淹建筑占地和受淹道路线长度；`continuous_flood_area_m2` 与 `blocked_roads` 保持 `null`。官方数据没有连续洪水面，受淹道路也不是已核实封路。

本次没有读取或运行任何 AI 预测，没有训练、调阈值、改 split、访问 Louisiana 或 future blind holdout，也没有改变 Gate 6/7 和 production readiness。

## 未通过原因

1. 固定区域缺少真实或赛事认可的社区边界。
2. 固定区域缺少真实、可追溯且带许可和日期的人口数据。
3. 因此五项风险指标不完整；`RiskCalculator` 必须拒绝计算，不能把缺失值当 0。
4. 当前 Windows Computer Use 环境返回空的 native app 列表，且运行时接口没有 native `getApp` 能力；未能启动或绑定 MapGIS 窗口。没有生成截图、MapGIS 原生查询日志或 GUI 验收 JSON，也没有伪造这些证据。

`scripts/validate_gate5.ps1 -RunDirectory runtime/acceptance/gate5-gt-20260912-01` 按预期返回退出码 2，列出风险、GUI 和 blocker。只有补齐两类真实数据、完成社区/人口/风险分析，并在授权 MapGIS GUI 中获得真实证据后才能复跑并考虑 PASS。
