# 系统架构

Java21洪涝插件运行于已安装MapGIS宿主。ICommand/Ribbon入口打开工作面板，通过Java HttpClient提交FastAPI任务并轮询。Python只处理影像数组，返回分类PNG、预览和像素统计；MapGIS适配层负责栅格格式转换、空间参考和原生网络分析。

| 层 | 现有组件 | 验证状态 |
|---|---|---|
| 科研训练 | Rasterio配准/标签，官方SiamUnet，配置训练/恢复 | GPU实际运行 |
| 图像推理 | fallback或显式siamunet-smoke，CUDA，FastAPI/CLI | API与跨进程测试通过 |
| 桌面交互 | ICommand/Ribbon/影像选择/任务进度/预览/空间化按钮 | SDK编译通过，授权阻塞现场运行 |
| GIS适配 | RasterDataset空间化、NetAnalyse权/障碍/路径 | 真实Javadoc+编译，未原生运行验收 |
| 业务 | 风险评分、资源排序、道路状态、HTML报告 | 单元测试；尚未接上真实空间统计 |
| 生命周期 | 安全进程记录、启动健康检查、失败清理、开发打包 | 实际AI启停和桌面授权失败清理通过 |

没有引入其他GIS平台作为最终GIS核心。自写EmergencyRouter只作可注入业务测试，不代表MapGIS路线功能已完成。任务状态目前仅在内存，服务重启后job_id不可查询；API限本机使用，尚无多用户认证。
