# GeoTIFF 地图加载验收（尚待实际宿主操作）

最新版本点击空间化后会在本次识别任务目录下建立`mapgis-UUID`目录，保存四类TIFF、flood_mask.tif、overlay.tif及spatial-result.json。清单只证明MapGIS读取的网格一致，不自动标记地图渲染、灾损或精度通过。目录中没有清单表示未完成全部输出，请查看错误提示。此批量路径已编译测试，尚待实际桌面验收。

先保存工作，在管理员PowerShell中执行scripts/stop_demo.ps1、scripts/build_mapgis_plugin.ps1、scripts/start_demo.ps1。

识别面板填写：

- 灾前：`C:\Users\33076\Desktop\高级开发\data\processed\geotiff-test-0_36_68\pre.tif`
- 灾后：`C:\Users\33076\Desktop\高级开发\data\processed\geotiff-test-0_36_68\post.tif`
- 输出：`C:\Users\33076\Desktop\高级开发\data\outputs\geotiff-test`

样本512×512，EPSG:4326。地理范围（西、南、东、北）：7.0150355805050575、50.48242027033169、7.019901454960709、50.48728614478734。

1. 激活主窗口的二维地图。
2. 在识别面板运行这对TIFF，成功后点击“空间化并加载 MapGIS”。
3. 确认图层出现、视图定位到数据范围，记录错误或成功截图。
4. 核对生成flood-georeferenced-*.tif的坐标系、范围和512×512尺寸；加载不代表模型精度达标。

已经验证：真实CUDA服务接受该TIFF对并生成512×512掩膜，任务96603ce9bbec4d999ab76f79d572b748成功。尚未验证：MapGIS原生空间化和地图显示，当前自动化会话非管理员且运行中桌面持有旧JAR。

输入是SpaceNet8官方Germany样本，经隔离科研环境Rasterio准备的同网格测试夹具，provenance.json保存源文件哈希与变换。它不是最终MapGIS配准流程的实现或验收证据。运行时AI服务未引入Rasterio。该样本也不是官方独立测试集。

页面已改为异步查询health显示真实后端/设备，普通PNG不再启用空间化按钮。新代码需重新构建并启动，不能在旧进程自动生效。

## 模型注意

查明旧训练错误：将flooded=null排除，而锁定上游baseline/data_prep/geojson_prep.py将其归为未受淹。已修正，并新增测试及预处理哈希，防止用不同标签语义续训旧检查点。

修正模型独立保存于models/checkpoints/spacenet8-label-fix；40轮训练完成，测试集非受淹建筑/道路IoU仍0，受淹类别无真值且无预测时为null。未替换在线烟测模型。数据少、类别覆盖不足、128像素缩放及道路未做官方缓冲仍限制质量，不可宣称精度提升或部署就绪。
