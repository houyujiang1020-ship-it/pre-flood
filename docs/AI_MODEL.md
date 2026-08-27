# 模型与训练

默认服务 spectral-change-fallback 为变化检测，不是神经网络 checkpoint；production_checkpoint_loaded=false。像素统计不能当建筑栋数、路段数或平方公里。

研究烟测 app/training/train_smoke.py 使用锁定上游 SiamUnet_diff、真实配对和4通道标签，按地理网格配准，忽略未知 flooded；至少两组完整数据，最后一组仅验证。默认128×128、batch1、2epochs，CUDA 可用则自动启用，也可传 --device cuda 禁止静默回落 CPU。

```powershell
.\scripts\download_data.ps1 -Mode sample -Count 2
.\scripts\train_smoke.ps1
```

隔离 .venv-training 安装 PyTorch2.5.1+cu121、NumPy1.26.4、Pillow11.3.0、Rasterio1.4.3。官方 wheel 索引 https://download.pytorch.org/whl/cu121/ 。不得把研究 GIS 依赖装入最终 AI 环境。

产物 models/checkpoints/spacenet8-smoke：smoke_model.pth、training_report.json、validation_prediction.npy。脚本保存后重载推理，记录真实 loss/微平均 IoU；smoke_only=true、production_ready=false，不代表部署精度。

四类仅覆盖建筑/道路洪水状态；受淹要素并集不是完整开放水面的洪水范围。

## 配置训练与恢复

已实现 scripts/train_full.ps1，读取 config/training.example.json，按显式区域/标签列表分割训练、验证、测试，拒绝重叠。逐样本加载以控制内存，保存 last_model.pth（优化器/RNG/进度）与按验证loss选择的 best_model.pth；测试不用于选权重。默认配置只是6组官方样本的管线验证，不代表全数据训练。

```powershell
.\scripts\download_data.ps1 -Mode sample -Count 6
.\scripts\train_full.ps1
.\scripts\train_full.ps1 -Resume -Epochs 3
```

2026-08-27已实测2epochs及恢复第3轮，最佳验证loss0.462234；各有效类别IoU仍0。测试是公开德国训练区留出样本，不是官方Louisiana-West测试精度。完整数据与官方道路缓冲预处理、高精度评估仍未完成。

## 可选模型 API

```powershell
.\scripts\setup_torch.ps1 -Environment Training
.\scripts\setup_torch.ps1 -Environment Inference
$env:FLOODGUARD_CONFIG = (Resolve-Path config/application.smoke.yaml).Path
.\scripts\start_ai.ps1
```

默认无本地配置仍使用fallback。显式配置缺失或模型加载失败时health返回503，不静默回退。烟测后端使用纯PyTorch/Pillow，要求输入已在相同空间网格；不会引入Rasterio。`tests/integration/verify_torch_smoke.py` 已验证真实模型的FastAPI任务输出（TestClient，不是跨进程或GIS E2E）。
