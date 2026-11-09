# MapGIS-FloodGuard 第八阶段最终验收报告

当前状态：**NOT_READY**。

## 1. 项目简介
面向城市洪涝灾害的智能分析与应急决策桌面系统。

## 2. 系统架构
Java + MapGIS SDK 桌面工作台经 FastAPI/PyTorch 接入 AI 检测，串联灾损、风险、路网与资源调度。

## 3. MapGIS 二次开发内容
地图使用官方 MapControl；空间对象、叠加、网络分析和专题显示由 MapGIS SDK 提供。

## 4. AI 模块
AI 对象预测通过 flood_prediction.json 进入灾损分析。正式案例推理或回放仍需在官方宿主记录。

## 5. GIS 空间分析与风险评估
风险公式为 0.4 建筑 + 0.3 人口 + 0.2 道路 + 0.1 资源距离。人口项须使用真实洪水面和 MapGIS 人口格网叠加。

## 6. 应急决策流程
道路封闭状态进入 MapGIS 原生路网阻抗，再计算绕行路线和资源匹配。

## 7. 真实运行环境
启动记录：`startup_log.json`；环境报告：`submission/final_environment_report.json`。
本次官方宿主探针在管理员权限预检处停止，未进入许可证、MapControl 与地图渲染验证。

## 8. 正式案例说明
尚无已核验正式案例清单

## 9. 测试与指标结果
本轮 SDK 插件构建成功；静态注册探针通过。正式案例指标需要宿主实际运行后由 FinalValidator 复核。

| 验收项 | 状态 |
|---|---|
| mapgis_license | 未核验/未通过 |
| mapcontrol | 未核验/未通过 |
| map_rendered | 未核验/未通过 |
| official_data | 未核验/未通过 |
| flood_analysis | 未核验/未通过 |
| risk_analysis | 未核验/未通过 |
| route_planning | 未核验/未通过 |
| resource_dispatch | 未核验/未通过 |
| report_generated | 未核验/未通过 |
| screenshots_complete | 未核验/未通过 |
| submission_sources | 通过 |

## 10. 运行截图
尚无官方宿主运行截图

## 11. 问题记录与后续验收
1. 在管理员权限且有授权的 MapGIS 宿主运行插件，留存许可证状态与真实地图渲染记录。
2. 补齐 `OfficialDemoScenario/official_scenario.json` 及全部正式数据的来源、SHA-256 和 MapGIS 原生图层 URL。
3. 执行完整演练并人工检查八张必需截图及地图数据补充图、人口叠加结果、路线和报告；更新独立复核结果。
