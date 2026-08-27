# MapGIS-FloodGuard

《基于 MapGIS 与多源遥感智能解译的城市洪涝灾害态势感知与应急决策系统》。当前处于核心 MVP 建设阶段。

## 当前完成度

已验证：官方SpaceNet8样本、RTX4050烟测训练与重载、配置训练/恢复、PyTorch/FastAPI推理、Java跨进程调用、MapGIS插件编译、业务层单元测试。

未完成：MapGIS授权验证、插件现场加载、真实空间叠加/道路匹配/动态阻抗与完整业务GUI、GIS路线和报告E2E。烟测IoU=0，没有可用精度结论。当前是开发验证工程，不是已验收参赛成品。

## 环境准备

```powershell
Set-Location -LiteralPath 'C:\Users\33076\Desktop\高级开发'
.\scripts\check_env.ps1
.\scripts\setup_python.ps1
.\scripts\setup_java.ps1
.\scripts\setup_torch.ps1 -Environment Training
.\scripts\setup_torch.ps1 -Environment Inference
```

Python3.10；核心Java17；已安装MapGIS10.7.10.10宿主及SDK使用Java21。普通工具安装方式见scripts；MapGIS专有软件和授权不能由开源依赖安装替代。GPU wheel按官方SHA256校验。训练Rasterio仅安装于.venv-training，不进入最终推理环境。

## 数据与模型

```powershell
.\scripts\download_data.ps1 -Mode sample -Count 6
.\scripts\train_smoke.ps1
.\scripts\train_full.ps1
.\scripts\train_full.ps1 -Resume -Epochs 3
```

train_full默认配置仍只用6组数据检验流程。扩展训练请编辑独立JSON配置并使用-Config，不覆盖已存在的训练目录；恢复时配置/架构须匹配。没有官方现成checkpoint下载链接，不虚构download_models；模型由真实训练生成。详细来源、数据许可及评估范围见docs/DATASET.md和AI_MODEL.md。

## 启动与停止

```powershell
.\scripts\build_mapgis_plugin.ps1
.\scripts\start_demo.ps1
.\scripts\stop_demo.ps1
```

默认启动真实烟测模型和官方MapGIS开发宿主。脚本从已安装宿主生成独立UI配置，追加洪涝Ribbon，不改原软件/授权。若授权失败，明确报错并清理本次进程；不能认为桌面Demo成功。

只调试AI时使用 `start_demo.ps1 -AiOnly`；模型状态可查 http://127.0.0.1:8765/health 。推理要求灾前灾后已在同一空间网格，原始官方影像尺寸不同，不能直接拿来逐像素比较。研究烟测导出的配准PNG只作API验证，不冒充GIS图层。

独立默认fallback服务：`start_ai.ps1`。要选择真实烟测模型，设置环境变量FLOODGUARD_CONFIG为config/application.smoke.yaml绝对路径再启动服务。未配置时不会偷偷切换模型；请求格式见docs/API.md。

## 测试与打包

```powershell
.\scripts\run_tests.ps1
.\scripts\run_model_e2e.ps1
.venv-training\Scripts\python.exe app\training\test_training.py
.\scripts\verify_mapgis_host.ps1
.\scripts\build_release.ps1
```

模型E2E是Java/HTTP/真实GPU推理，不含MapGIS空间业务。宿主验证目前预期失败，原因见BLOCKERS.md。build_release输出明确标注NOT COMPETITION-READY的开发包，包含最小权重、官方样本、代码、文档和SHA256清单，不含MapGIS专有JAR、许可证、虚拟环境或个人配置。

最终GIS联调验收步骤见docs/MAPGIS_INTEGRATION.md；不要把编译通过等同于原生计算通过。

真实完成度见 `PROJECT_STATUS.md`，外部依赖见 `BLOCKERS.md`，续跑入口见 `NEXT_TASK.md`。
