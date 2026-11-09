# AI正式管线小规模对照 — 2026-09-12

本轮把诊断中验证过的GroupNorm接入训练和AI服务的同一模型构造器。checkpoint新增normalization、group数、model_id、四类阈值、trained_at、metrics_file、git commit及dataset split hash；API按checkpoint记录的阈值推理，`GET /model/info`返回这些真实字段。旧BatchNorm checkpoint缺少新字段时明确按batchnorm兼容读取，权重结构不会混用。

## Germany 10/4试验

三组均使用同一Germany训练10张、验证4张、256像素、12 epoch、seed 20260912；未读取test或Louisiana。目的仅是比较管线组合，不做精度验收。

| 运行 | GroupNorm | 正类采样 | 像素正类权重 | 最佳验证macro IoU |
| --- | --- | --- | --- | ---: |
| gn-pilot | 是 | 是 | 是，最高8 | .012844 |
| gn-sampler-pilot | 是 | 是 | 否 | .004641 |
| gn-loss-pilot | 是 | 否 | 是，最高8 | .004912 |

三者都不具备候选价值。第一个组合同时改变采样概率和损失权重，发生明显过补偿：最佳附近受淹道路预测远多于真值，正常类常为零预测。训练器现默认拒绝同时启用两种再平衡，只有显式、经审阅的override才能运行。后两项说明12 epoch小数据不能据此选出采样或损失方案；不继续加epoch，也不把结果推广到153/44完整划分。

## API一致性

`config/application.gn-pilot-20260912.yaml`加载实际GN best checkpoint；CUDA重载测试通过。真实API推理输出在`data/outputs/gn-pilot-api-20260912/verification.json`：checkpoint SHA256 `4e4dce78661fa1ac3b51947178d4bc1aac241325b76ee52303782edaac4207fb`，模型身份、normalization、阈值、split hash及metrics路径均返回；inference_verified=true、accuracy_verified=false、production_ready=false。

## 可见性审阅准备

`prepare_visibility_review.py`实际审计Germany train153+validation44，共197张；80张存在post2。v2清单包含pre参考及每个post候选的SHA256、valid比例、亮度、近白比例、通道差和梯度，只用于排序审阅，自动排除数为0。优先Top20已逐项视觉审阅：12项reject、3项post1、5项post2。`validate_visibility_review.py`确认20项引用、候选和证据有效；177项pending，因此training_split_frozen=false。

训练配置现在允许每个split条目显式指定`post_event_column`，只接受官方配对表的post1/post2且必须存在。正式选择仍需可追溯审阅结果；没有根据Louisiana效果或未校准分数自动替换。

## 结论

GroupNorm的训练、checkpoint、服务重载、身份和推理路径已经贯通。小规模对照未产生质量候选，证明归一化修复本身不足以解决模型精度。下一步应先完成197张可见性审阅并冻结post选择，再在153/44上做两个预声明实验：GN+均匀采样+温和损失，以及GN+正类采样+普通BCE/Dice。两者不能同时重复补偿；Louisiana继续不参与选择。
