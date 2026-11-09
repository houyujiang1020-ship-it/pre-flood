# 标签与空间对齐审计（2026-08-30）

本次实际执行 `app/training/diagnose_spatial_pipeline.py`，CPU 单线程；没有训练 GPU、下载或修改源数据。固定 seed=20260830，从当前 Germany train+validation 抽20组，Louisiana研究evaluation抽20组。复现命令：

```powershell
.\.venv-training\Scripts\python.exe app/training/diagnose_spatial_pipeline.py
```

证据：`experiments/diagnostics/alignment/alignment_report.json`、同目录6张四联图、`experiments/diagnostics/reports/class_distribution.json`及CSV。40组清单、原始CRS/transform/pixel size/extent/width/height、标签目标transform、UTM分区及有效比例均在JSON中。

## 空间检查结论及限制

40/40原始pre/post网格不相同；40/40 post地理extent转换到pre CRS后覆盖pre extent的比例为1.0。实际代码不是将post直接resize：`train_smoke.load_pair`用pre的缩放transform作为目标网格，对post逐波段使用rasterio.reproject，双线性采样；mask另用nearest重投影。GeoJSON按EPSG:4326解释并转换到目标网格。此次重新计算的40组pre/post/GT/valid与已有缓存逐tensor完全一致；最低valid比例0.995861。没有证据支持当前缓存损坏、错用不同瓦片或仅resize假配准的指控。

这些结果仅证明地理参考/栅格化/缓存一致，不能证明地物级亚像素配准正确。标签源CRS是现行源码对GeoJSON的解释，并不是新增官方CRS认证。尚未进行40组控制点残差、正射误差或全801组人工验收；配准最终门禁不能仅据此置pass。

## 6张图的实际目视审阅

图顺序：左上pre、右上reprojected post、左下GT、右下pre+GT。黄色=非淹建筑，红色=受淹建筑，青色=非淹道路，紫色=受淹道路；叠加中后绘制的颜色可能遮住其他类别，不能据彩色图否认多标签重叠。

| 区域/标签 | 实际看到的证据 | 边界 |
|---|---|---|
| Germany 0_17_67 | 主干道路和弯道标注大体随影像道路；pre/post同一林地、道路形态 | 季节/树冠差异明显，未量化控制点偏移 |
| Germany 0_25_68 | 上方道路交汇及下方道路标注对应可见道路 | post大范围云遮挡，不能用不可见地物宣称配准通过 |
| Germany 0_32_58 | 弯曲道路GT沿pre道路，post对应相同道路 | 色调、亮度差异明显 |
| Louisiana 2_18_52 | 受淹建筑GT对应沿路房屋，紫色道路对应道路 | post有霾/云和灾后变化，GT不是模型输出 |
| Louisiana 1_6_100 | pre住宅和主路对应黄色/青色标注 | post几乎整幅云遮挡，缺乏可用地物对应证据 |
| Louisiana 1_8_89 | 上方住宅区环路标注对应pre环路 | post显著云影/曝光差异，建筑标注不完整不能据肉眼补标 |

审阅为本次代理视觉检查，不是独立人工签字验收。没有对每栋建筑、每段道路核验。6张图全部真实生成并打开查看，不能外推为40组全部视觉通过。

**新增明确风险：valid只表示nodata有效，不表示地物可见。** 上述云遮挡区域仍进入监督；现行代码只采用`post-event image 1`，不选择配对表中的第二post，也没有云/阴影质量筛选。该问题是有图像证据的数据质量风险，不能据6张图估计全数据云量，更不能单独断言是全部低精度主因。后续先做train/validation质量筛选协议，避免按反复查看的Louisiana效果选数据。

## 道路缓冲与标签语义

`buffered_road`按WGS84几何中心选择UTM分区，经`always_xy=True`投影到米单位，在UTM中buffer(3.0)，再转回目标CRS。因此3m是半径、总宽约6m，不是在经纬度中buffer3度。随机样本UTM区在报告中逐组记录。栅格化为`all_touched=False`；道路和建筑分别按四个二值channel栅格化，没有把建筑数/道路数等同像素数。

固定本地上游 `upstream/SpaceNet8/baseline/data_prep/create_masks.py`实际主流程也设置`road_buffer_distance=3.0`；不要被该文件辅助函数默认值2.0误导。上游先把建筑、道路各自以mask_id写入单波段，再用值1/2拆成non-flooded/flooded，因此同种地物两语义不会在单像素同时为1；默认替换栅格化使交叠处随要素顺序覆盖，并没有明确“受淹始终优先”的规则。

当前实现独立烧写四通道，允许相邻不同属性道路的3m buffer相交时两类都为1。这与独立sigmoid+BCE数学上相容，**不是自动判定训练bug**，但不完全等价于官方单波段拆分语义。实际有效像素中的道路两语义重叠train=3426、validation=1351、Louisiana=2776；对应道路union比例约0.344%、0.389%、0.079%。建筑两语义重叠均0。建筑/道路跨类型也能重叠（train4103、validation799、evaluation1551）。重叠量不足以解释整体极低IoU；如以后切换互斥输出或官方标签策略，须明确版本并重新生成缓存，不能在本轮悄悄改变旧实验。

## 全缓存类别分布

统计覆盖153 train、44 validation、599 Louisiana evaluation，共796组（202德国中原有5个空间边界tile不属于split）。仅有效监督像素计数；building/road为各自两语义union，background为四通道全0；各列不能简单相加当互斥类别。

| split | valid像素 | background | building | road | flooded building | flooded road | 有FB tile | 有FR tile | 纯背景tile |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Germany train | 39,661,562 | 38,057,751 | 613,378 | 994,536 | 166,213 | 189,208 | 35/153 | 49/153 | 0/153 |
| Germany validation | 11,533,945 | 11,018,410 | 169,171 | 347,163 | 72,543 | 96,172 | 7/44 | 12/44 | 0/44 |
| Louisiana evaluation | 156,180,545 | 149,568,927 | 3,105,360 | 3,507,809 | 373,197 | 504,631 | 88/599 | 127/599 | 0/599 |

train背景像素95.96%；FB像素0.419%、FR像素0.477%。少数类稀疏是真实问题，但并非“很多纯背景tile”：纯背景tile实际为0。采样应提高含受淹类tile/局部patch的曝光率，不能把所有无受淹tile误标为纯背景；分组输入已保存`experiments/diagnostics/sampling/tile_categories.json`。

Louisiana已经重复用于研究比较，不再是blind holdout。本审计只诊断，不重设生产阈值、不宣布模型精度通过。
