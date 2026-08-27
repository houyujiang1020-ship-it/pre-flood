# 演示运行

先按README准备依赖、6组官方数据、smoke checkpoint和插件JAR。

`scripts/start_demo.ps1` 启动独立CUDA AI服务，等待模型health，再通过官方DesktopLauncher --developer --custom-ui启动MapGIS。项目生成的XML保留宿主基础配置并增加洪涝入口。`stop_demo.ps1`核对PID、创建时间、命令行后只关闭自身进程树。

2026-08-27实际结果：AI启动成功；MapGIS授权失败后脚本清理AI和Java，测试端口无遗留监听。完整Demo目前未通过。

可用的独立工程演示：`start_demo.ps1 -AiOnly`，使用models/checkpoints/spacenet8-smoke/validation_pre.png和validation_post.png提交API。这是官方验证影像的科研配准像素夹具，没有可供最终GIS验收的空间参考。结束运行stop_demo。

授权通过后在“洪涝应急”Ribbon打开识别面板，选择由MapGIS配准的两期GeoTIFF，推理后点击空间化并加载，人工核对地理位置。后续灾损/路线/资源/报告面板尚未完成，因此不能按完整比赛流程演示。
