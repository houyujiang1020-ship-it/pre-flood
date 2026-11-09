# GitHub 仓库整理说明

## 目录导航

| 路径 | 内容 |
| --- | --- |
| `app/ai-service/` | FastAPI 推理服务及测试 |
| `app/mapgis-flood-desktop/` | Java/MapGIS 桌面端及测试 |
| `app/training/` | 模型训练与研究代码 |
| `config/` | 示例配置和实验配置；本机配置不提交 |
| `scripts/` | 环境准备、构建、运行和验证脚本 |
| `tests/`、`tools/`、`pseudo_label/` | 跨模块测试、辅助工具和伪标签代码 |
| `docs/`、`reports/` | 架构、实验过程和可审阅的文本报告 |

## 不进入 GitHub 的本地文件

训练数据从原发布方获取，下载链接和目录约定见 [数据集说明](DATASET.md)。权重的来源、配置和本地训练方式见 [模型权重说明](AI_MODEL.md)。下载数据、权重、比赛交付材料、虚拟环境、训练产物和构建缓存保留在本机。运行桌面端需要在本机安装并授权 MapGIS 宿主和 SDK。

## 发布前检查

在仓库根目录运行：

```powershell
git status --short
git ls-files --others --exclude-standard
git diff --check
```

提交配置前请核对示例值和实验参数。密钥与本机凭据保存在本地配置中。
