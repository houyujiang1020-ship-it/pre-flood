# Gate 5 Final Acceptance — Phase 2

日期：2026-09-12。最终状态：**BLOCKED**。Gate 5 validator 退出码为 **2**，competition readiness 为 **4/9**。

## 1. 固定 AOI 在哪里？

SpaceNet8 Germany `0_41_59`，WGS84 bbox `[7.0393649528, 50.5262131404, 7.0442308272, 50.5310790149]`，中心点 `(7.0417978900, 50.5286460777)`；EPSG:32632 bbox `[361031.832, 5598966.768, 361390.956, 5599516.868]`。BKG 官方 WFS 空间查询返回唯一相交 Gemeinde：Dernau，AGS `07131017`，且 Gemeinde 面完整覆盖 AOI bbox。

## 2–4. Community 与 population 来源

Community 来自 BKG `VG250-EW` 的 `vg250_gem` 官方 WFS，数据时点 2024-12-31，行政层级 Gemeinde，许可 `Datenlizenz Deutschland – Namensnennung – Version 2.0`。原始响应 SHA-256 为 `86bd33e0548829d728f239f01db53e6616a7e4053d565df893d42ae0d158cb1a`。Dernau 官方 2024 人口为 1,495，只作行政单元总量交叉核对。

AOI 人口来自 Destatis Zensus 2022 官方 `Bevölkerungszahl 100m-Gitter`，人口年份 2022，原始 ZIP SHA-256 为 `1a8428d31eab264c8717bfdcbf40fbd66c217edb2e2a98d0e67741bd8a1a941a`。15 个有值格网与 AOI 相交。

## 5. 人口估算方法

配置为 `config/gate5_population_method.yaml`，SHA-256 `6aa6f65b93ac6e6951e81b7d1a80631565342394fecc351ef1b7adfece778c31`。公式：

`Σ(格网人口 × AOI相交面积比例 × 格网内受淹建筑占地 / 格网内全部标签建筑占地)`

这是 100 米格网内建筑面积加权估算，不是登记受灾人口。边缘格网假设人口在格网内均匀；无标签建筑的格网不分配受影响人口。正式验收仍要求 MapGIS 重现格网、建筑、AOI 和社区相交。

## 6–9. 实体结果是否一致？

保持一致：建筑 `82 / 76`，道路 `20 / 14`；受淹建筑占地 `12,281.684 m²`；受影响道路长度 `2,446.522 m`。没有重新实现或改变 Phase 1 核心。

## 10–11. 为什么两个字段仍为 null？

`continuous_flood_area = null`，因为 SpaceNet8 只给对象级 flooded 属性，没有连续洪水面。`blocked_road_count = null`，因为受淹道路不等于有封闭真值或人工封路核查。没有用建筑面积、道路缓冲或零值替代缺失语义。

## 12–13. 社区与人口结果

AOI 只位于一个真实单元 Dernau，没有人工拆分社区。参考准备结果：82/76 个建筑和 20/14 条道路均归于 Dernau；全局道路实体按 ID 去重，社区道路长度按真实相交线段口径。Zensus 格网估算 AOI 人口 `125.182`，估算受影响人口 `115.077`。

上述 community/population 结果状态为 `REFERENCE_PREPARATION`。Python 仅完成下载、schema、哈希和参考转换；正式 MapGIS 空间相交尚未运行，因此不能标为业务验收结果。

## 14. Risk 结果

Risk 仍为 `BLOCKED`，没有 score 或 level。正式权重仍为 0.30/0.25/0.20/0.15/0.10，没有重新发明权重。当前可追溯的建筑、道路和人口量已经登记，但仍缺：不依赖连续洪水面的正式 flood 指标定义、MapGIS 验证的道路可达性、真实医疗可达性，以及 MapGIS 对 community/population 相交的复算。`RiskCalculator` 要求五项完整指标，缺失值不能记为 0。

## 15. MapGIS GUI 证据

Java 21 SDK 插件已构建，56 项 SDK 测试和注册 probe 通过；最新 JAR SHA-256 为 `bd6563757f02ea5bc4d88db59ca8ba42c1c304b0d6935b27abaf33a32eb66dc8`。GUI 已增加明确的 `GT VALIDATION`/`AI PREDICTION` 模式；GT 模式禁用 AI 推理。

当前 Computer Use 环境再次返回空 native app 列表，无法绑定真实 MapGIS 窗口。七张截图、desktop.log、正式空间相交与专题表达均未生成。人工清单位于 `docs/GATE5_GUI_EVIDENCE_CHECKLIST.md`，空的 manifest 明确标为 pending，没有伪造截图。

## 16–17. Validator 与 readiness

`runtime/acceptance/gate5-phase2-20260912-01` 的 validator 退出码为 2，具体缺口为风险未完成、MapGIS GUI 缺失、七张截图缺失、blocker 未清和 `damage_analysis_completed != true`。重新审计结果仍为 4/9。未手工修改 readiness JSON。

Phase 2 已清除“community 数据缺失”和“population 数据缺失”两个原始 blocker。剩余闭环必须在真实授权 MapGIS 宿主中完成正式空间分析、GUI 证据，并补齐风险模型所需的真实道路/医疗可达性依据。
