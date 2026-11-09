# 模型权重与训练

仓库提供模型代码、配置和训练流程。权重文件在本机保存，不随仓库发布。下表列出服务支持的三种配置及所需的本地权重。

| 后端 | 权重与用途 | 配置 |
| --- | --- | --- |
| `spectral-change-fallback` | 默认影像变化检测，运行时无需模型权重 | [AI 服务说明](../app/ai-service/README.md) |
| `siamunet-smoke` | 从样本本地训练，生成 `models/checkpoints/spacenet8-smoke/smoke_model.pth`，用于验证训练和推理流程 | [application.smoke.yaml](../config/application.smoke.yaml) |
| `e4-research` | E4 固定研究检查点，路径为 `models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth` | [application.e4-research.yaml](../config/application.e4-research.yaml) |

E4 的 SHA-256 为 `ba2da68622d79683de2b6a9c30209c509d21cc44c1693e9118a061616c93e4bc`。服务校验该哈希，重新训练的候选需要按其自身身份评估。E4 缺少独立外部精度验证，目前是研究模型。像素统计不能当作建筑栋数、路段数或平方公里。[E4 研究与复现流程](MODEL_ACCURACY_PIPELINE.md)

## 在本机生成烟测权重

研究烟测 app/training/train_smoke.py 使用锁定上游 SiamUnet_diff、真实配对和4通道标签，按地理网格配准，忽略未知 flooded；至少两组完整数据，最后一组仅验证。默认128×128、batch1、2epochs，CUDA 可用则自动启用，也可传 --device cuda 禁止静默回落 CPU。

在仓库根目录执行以下命令。已有上游工作树时，按 [上游版本说明](UPSTREAM_LOCK.md) 核对提交即可。

```powershell
.\scripts\setup_python.ps1
.\scripts\setup_torch.ps1 -Environment Training
git clone https://github.com/SpaceNetChallenge/SpaceNet8.git upstream/SpaceNet8
git -C upstream/SpaceNet8 checkout 30ca30c2530c6a234d040f60a99a7366ff62d756
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
