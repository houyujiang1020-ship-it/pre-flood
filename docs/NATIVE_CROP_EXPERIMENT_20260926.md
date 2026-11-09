# E2 原分辨率裁块与重叠推理实验

日期：2026-09-26。实验检验 512 整图缩放是否是当前精度瓶颈。训练/验证 split、域平衡 sampler、SiamUnet_diff、GroupNorm8、BCE+0.5 Dice、学习率、30 epoch 和固定 0.5 阈值保持不变。

## 方法与公平基线

- 原始影像为 1300×1300；对齐到 1280×1280，仅轻微缩放并保持 16 的倍数。
- 训练用 448×448 裁块，75% 概率围绕随机正类像素取样；验证用 448 窗口、336 stride，Hann 权重融合完整 1280 图。
- 715 组 compact cache 全部生成，RGB/label/valid 坐标同步；test 为空。
- 不能把 512 和 1280 栅格 IoU 直接比较。因此在训练前先把当前 512-trained research leader 放到同一 1280/448/336 口径重算，macro 为 0.052515。
- 预注册晋级条件：同口径 macro 至少增加 0.01、两类道路都改善、建筑类下降不超过 0.005。

## 结果

训练完成 30 epoch；最佳为 epoch 29。独立进程重载最佳 checkpoint 后复算一致。

| 1280 grid、448/336 tiled、固定 0.5 | 未淹建筑 | 受淹建筑 | 未淹道路 | 受淹道路 | macro |
| --- | ---: | ---: | ---: | ---: | ---: |
| 512-trained 旧模型同口径 | 0.09066 | **0.03229** | **0.06515** | **0.02196** | **0.05251** |
| E2 原分辨率裁块模型 | **0.10565** | 0.00012 | 0.01431 | 0.00000 | 0.03002 |

E2 macro 下降 0.02250；受淹建筑、两类道路显著退化，受淹道路完全没有越过 0.5。`promotion=rejected`。该结果与先前分辨率审计一致：当前瓶颈不是简单的输入缩放；在缺少结构辅助监督时，原分辨率会增加背景占比并减少单个 crop 的上下文。

checkpoint：`models/experiments/germany-louisiana-native-crop-20260926/best_model.pth`  
SHA-256：`575ba7ef3abe222443b40afca092f3aa0da3fc8bc09d8c9f202d7b456c2efd0d`  
独立复算：`models/experiments/germany-louisiana-native-crop-20260926/independent_reload_validation.json`  
公平基线：`experiments/germany-louisiana-native-crop-20260926/baseline_native_tiled_evaluation.json`

## 决定

- 停止继续搜索 crop size、stride 或增加 E2 epoch；保留 512 非 EMA 域平衡模型为 research leader。
- compact 原分辨率缓存保留，供将来已有强 foundation 模型后验证多尺度推理；当前下一步回到 512 开发网格，执行建筑边界/接触与道路骨架/交叉口辅助监督。
- test 未使用，`production_ready=false`。
