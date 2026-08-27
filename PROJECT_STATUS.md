# MapGIS-FloodGuard 项目状态

更新时间：2026-08-27

本轮已跑通官方样本 GPU 烟测训练、checkpoint 保存/重载和 PyTorch API 推理；IoU=0，绝不代表可用精度。模型/像素结果与 GIS 业务验收分开记录。

## Environment
- [x] 环境检查脚本可运行
- [x] Python 环境可复现
- [x] Java 环境可复现
- [x] MapGIS SDK 状态明确

## Upstream
- [x] MapGIS-Desktop-Java 已克隆并锁定
- [x] SpaceNet8 已获取并锁定
- [ ] 上游许可证与依赖已审计

## AI
- [x] 官方 SpaceNet8 配对样本下载校验
- [x] 官方 SiamUnet 架构 GPU 烟测训练及重载
- [x] SpaceNet8 最小真实模型 API 推理（烟测权重）
- [ ] 模型精度验证及完整数据训练
- [x] FastAPI health
- [x] FastAPI inference
- [x] CLI predict
- [x] AI Service 自动测试

## MapGIS
- [x] 洪涝插件基于已安装 SDK 编译打包
- [ ] 上游完整 Desktop 工程构建（旧源码 JavaFX 兼容问题未完成）
- [x] 影像选择/进度/取消等待面板编译
- [ ] 洪涝插件加载
- [x] Java 调用 AI 服务
- [ ] AI 结果加载至 MapGIS

## Product
- [ ] 灾损与道路阻断分析
- [ ] 安全救援路线
- [ ] 资源调度与风险评价
- [ ] 自动灾情报告
- [ ] 一键 Demo 与 E2E
- [ ] 发布包

## 开发交付（不是参赛完成）
- [x] 真实模型识别记录HTML导出与内嵌预览（非完整GIS灾情报告）
- [x] 风险缺失指标/非法数值拒绝计算回归
- [x] 官方GPU模型跨进程Java/HTTP推理测试
- [x] 配置训练2轮及恢复第3轮、留出评估
- [x] 独立MapGIS应用XML/Ribbon入口生成与回归
- [x] AI一键启停及桌面授权失败后的安全清理
- [x] 开发包打包，明确标注NOT COMPETITION-READY

参赛级发布包与完整GIS E2E仍保持未完成。最新源码阶段提交见Git；可继续执行入口见NEXT_TASK.md。

> 只有实际运行验证后的项目才标记为完成。
