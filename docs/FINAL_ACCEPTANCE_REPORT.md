# 本轮真实验收报告 — 2026-08-30 AI诊断里程碑

## 2026-09-12 后续进展

GroupNorm训练、checkpoint身份、FastAPI重载及CUDA推理已贯通，但Germany10/4三组12epoch试验最佳macro仅.012844，仍无候选。可见性v2清单197项，Top20审阅完成、177待审，split未冻结。新增preflight与competition_acceptance并实测生成11文件验收包；readiness仍4/9，production/真实台账/完整GIS业务没有新增pass。详情见`AI_PIPELINE_PILOT_20260912.md`与`NEXT_TASK.md`。

**这是诊断冲刺交付，不是RC1或完整参赛系统终验通过。** 4/9门禁不变；本轮没有新正式模型、真实资源台账或授权宿主GUI完整业务验收。

## 1. 已真实通过的内容

保留现有宿主证据：原生NetCls拓扑及持久化、投影几何长度/演练阻抗、资源端点绑定及基线/封路路线、灾前灾后结果地图显示。证据文件均仍存在，见`runtime/competition-readiness-evidence-20260830.json`。

本轮新增真实执行：2/4/8固定样本记忆测试、同权重BN干预、GN对照、历史模型反证、40组空间/缓存审计、796组类别统计、8组分辨率实验、正类采样器和完整回归。详见`AI_PIPELINE_DIAGNOSIS.md`。

## 2. 研究功能与当前精度

GN诊断模型在2/4/8固定crop的平均IoU为98.17%/95.93%/97.77%，仅表示记忆能力，绝不是泛化或比赛精度。现有正式研究基线的Louisiana599评估已经被重复查看，不再是盲holdout。

tempered旧模型的校准四类IoU为17.93%/1.88%/9.56%/2.53%，macro约7.98%；受淹道路precision约2.73%，不合格。当前在线API未被替换，不把这些校准指标当作线上API验收结果。

## 3. checkpoint与身份

历史完整研究候选：`models/checkpoints/full-germany-tempered-20260830/best_model.pth`，选中epoch34。

SHA256：`d1e073d9aef8129f30c2f8e7667684d493c2646afd7679e675ac26d4851a315c`。

GN诊断模型分别在`experiments/diagnostics/overfit/groupnorm-20260830-v1/patches-{2,4,8}/best_model.pth`，各自`report.json`记录SHA256；没有promote到production，也没有让旧API按旧架构误加载GN。

## 4. 数据与来源

使用用户已有`11`中的SpaceNet8官方公开Germany202、Louisiana599配对数据，不重复下载。原有空间划分为Germany train153/validation44、边界剔除5，Louisiana599研究evaluation；本轮沿用其缓存做诊断。来源/源文件SHA256见`data/processed/full-audit-20260830/audit.json`和本轮patch_manifest。

SpaceNet8受淹结构标签不是完整洪水边界。诊断图中GT明确为标注，未冒充AI预测。没有编造社区、人口或全洪水面积。

## 5. 资源

当前道路/建筑来自SpaceNet8公开数据；三个车辆组仍为显式演练资源。没有新增“真实车辆容量”或赛事认可台账。资源可达性历史演练通过不意味着真实派单能力或所有资源边界场景正式验收通过。

## 6. MapGIS原生能力与第三方边界

既有原生流程包括HDF数据库、SFeatureCls导入/投影、NetCls建网/重开/映射、GeoLine几何长度、NetAnalyse路线，以及栅格地理参考和地图显示。原生空间查询/矢量化代码存在不等于完整灾损验收已完成。JNI前置网络/权值/绑定/吸附等保护没有绕过。

PyTorch用于AI；Rasterio、Shapely、pyproj仅在隔离科研训练/诊断预处理环境使用，不替代最终MapGIS分析/路网，不引入QGIS、GeoServer、OSMnx或PostGIS。

## 7. 测试

`scripts/run_tests.ps1`本轮基线与最终均退出0。最终真实输出见`logs/diagnostic-final-regression.log`：

| 类别 | 本轮结果 |
| --- | --- |
| AI service pytest | 8 passed |
| 项目脚本pytest（含新门禁/采样测试） | 33 passed |
| 训练逻辑unittest | 11 passed |
| Java17核心 | 53，0失败/错误 |
| Java→AI HTTP集成 | 1，0失败/错误 |
| Java21安装SDK | 55，0失败/错误 |
| SDK插件注册探针 | 通过，明确GUI not tested |

联合脚本现在包含隔离训练环境测试，不再遗漏training logic。构建更新了target JAR，但未新启/重启授权GUI，不把构建当作现场业务验收。GN checkpoint概率重载一致、FP32批量不变性检查通过；初始TF32数值差异严格检查失败证据也保留在同目录。

## 8. Gate与剩余blocker

readiness **4/9，competition_ready=false**。新增schema v2记录每gate的status、evidence列表、validated_at及notes；现存证据才可能pass。离线模型验收配置分research/production，正式批准阈值缺失时失败关闭；当前两个层级均未通过，`production_ready=false`。

剩余：完整洪水范围/社区人口来源、20建筑原生与独立核验、正式道路/资源/报告闭环；GN新架构正式集成和train/validation质量控制；地物级配准验收；真正未污染holdout/独立评估；真实资源来源及容量；授权MapGIS宿主完整业务终验。故未制作或宣称RC1。

## 9. 本轮低精度原因判断

最强因果证据是共享BN训练/推理统计失配，GN小样本修复验证通过；但历史完整模型单改BN未改善，所以不能断言它是历史低精度的唯一主因。已证实的其他风险为少数类稀疏、云遮挡仍参与监督，且历史模型在训练区域抽样也表现差。当前证据未支持缓存错配或512大量道路标签消失。各因素对全域精度的贡献尚未量化；下一步应以这些证据设计有限train/validation对照，不能继续盲目加epoch。

交接入口：`NEXT_TASK.md`。所有本轮实验进程已完成，没有正在运行的正式训练。
