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

`.gitignore` 排除了虚拟环境、下载数据、模型权重、训练实验目录、运行输出、工具安装包、构建缓存和比赛交付材料。这些文件仍保留在本机。正式运行需要根据 `docs/DATASET.md` 准备数据，并在本机安装有授权的 MapGIS 宿主与 SDK。数据集、第三方软件或模型权重如需另行发布，请先核对许可。

## 发布前检查

在仓库根目录运行：

```powershell
git status --short
git ls-files --others --exclude-standard
git diff --check
```

提交配置前请核对示例值和实验参数。密钥与本机凭据保存在本地配置中。
