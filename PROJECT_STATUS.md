# MapGIS-FloodGuard 项目状态

更新时间：2026-08-27

新增资源推荐业务核心（类型/容量/可达性过滤、时间排序）及输入校验已通过自动测试；尚未接入 MapGIS 网络分析与桌面面板，产品项保持未完成。

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
- [ ] SpaceNet8 最小真实推理
- [x] FastAPI health
- [x] FastAPI inference
- [x] CLI predict
- [x] AI Service 自动测试

## MapGIS
- [x] Desktop 工程构建
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

> 只有实际运行验证后的项目才标记为完成。
