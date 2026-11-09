# Louisiana-West 无标签盲推理

## 数据与冻结边界

官方 SpaceNet8 Louisiana-West public test 已从
`C:\Users\33076\Downloads\Louisiana-West_Test_Public.tar.gz` 解压到
`data/external/Louisiana-West_Test_Public`。归档 SHA-256 为
`98548b72fa66ef179d9968e8e17cb416eedbe7673b4a1df54b3b624c76157fd`，包含 406 条完整的
pre/post1 配对，没有 GeoJSON 真值。来源页和 CC BY-SA 4.0 原文已保存并哈希。

`frozen-manifest.json` 在推理前锁定归档、来源许可、406 对影像、E4 checkpoint、固定 512
输入和四类 0.5 阈值。与 Germany 116 + Louisiana-East 599 张现有开发影像比较后，影像哈希
重复和正面积空间相交均为 0。manifest seal 为
`957906f4b554e796e831373623bde9e77e5dc1d1c66760678181f09c0668ab20`。

## 一次性结果

E4 对 406 对影像的一次性 CUDA 推理完成，处理有效像素 105,897,251。四类预测占比为：

| 类别 | 预测像素占比 | 有预测的瓦片 |
| --- | ---: | ---: |
| 未淹建筑 | 1.3744% | 353/406 |
| 受淹建筑 | 0.9383% | 351/406 |
| 未淹道路 | 1.4705% | 401/406 |
| 受淹道路 | 0.9230% | 396/406 |

四类均未整体塌缩，六张固定抽样中可见模型响应道路和部分屋顶，掩膜也没有覆盖整幅影像。但状态
通道存在严重重叠：受淹道路预测的 100% 同时属于未淹道路，受淹建筑预测约 99.56% 同时属于
未淹建筑。原始四通道输出因此不能直接解释为互斥状态图层。这与中部空间折上互斥建筑损失失败
共同说明，后续若有新的训练数据，应优先研究“对象定位 + 对象内状态分类”，并在新的开发折上
预注册评价；不得用本次 test 调阈值或选模型。

完整结果位于 `experiments/louisiana-west-blind-inference-20260926/e4-fixed05/`。报告 SHA-256 为
`7112debbc87c31e5c1af7e2293a4f2786b8be94f851054ab35237112db5f6881`。

## 结论边界

Louisiana-West public test 没有公开真值，因此本轮没有 IoU、F1、precision 或 recall。抽样外观和
非零预测不能证明识别正确。`accuracy_verified=false`、`production_ready=false`，E4 仍只是在
Germany 开发验证上的 research leader。本数据以后不得进入训练、校准、checkpoint 选择或门禁阈值选择。
