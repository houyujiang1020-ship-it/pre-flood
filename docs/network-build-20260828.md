# 2026-08-28 原生几何建网返回 0 排查

## 最新现场：创建成功，重开对象生命周期错误

`mapgis-00f71b1b-69a1-4a84-8e9a-3b905b8cf882` 的记录显示数据集 ID=5、网络创建返回 ID=7，失败发生在 verify_persisted_network，而非创建阶段。
检查本机 mapgis_geodatabase.jar 的 NetCls 字节码确认：close 调用 jni_DeleteObj 并 setHandle(0)，open 在 handle=0 时直接返回 0。此前新增验收错误地重用了已关闭对象。
已改为 close 后重新 new NetCls(db)，再 open(networkId,1)，记录关闭及重开返回值。后续原生目录、节点边和全部道路映射检查仍保留；本轮未取得新的原生验收结果，不能声称全部建网流程已通过。

## 最新复核：要素数据集遗漏

`mapgis-c153de27-3fa8-4eb8-872b-4cd93d89532e/network-build.json` 确认关闭输入类后仍失败；投影 WKT 是 EPSG:32632，范围约 E361037–361378、N5598971–5599516，持久化道路 20 条。因此此前句柄占用假设没有解决问题。

进一步核对官方 `GDBCatalogPane.java` 1759–1782 行：建网菜单属于要素数据集，查询该数据集的线类，再把真实 dsID 传给 CreateNetclsDialog。原实现遗漏了该层，一直使用 dsID=0。

本轮按官方流程创建 `exercise_transport` 要素数据集，使用道路投影后的空间参考 ID，将新建道路归入其中，关闭重开后校验数据集归属、目录枚举及数量。建网使用该真实 ID。网络创建后还会关闭重开、核验目录登记、边节点非空和所有道路子边映射。未通过任何一步都不会标记成功。新增四项纯 Java 前置检查测试；它们不代替原生接口验收。

原生宿主现场复测尚未执行，不能保证返回 0 已彻底消除。此次独立构建位于 `runtime/network-dataset-build`，不热替换运行中的插件。保存并关闭 MapGIS 后按 `stop_demo.ps1`、`build_mapgis_plugin.ps1`、`start_demo.ps1` 顺序更新。另修正启动失败提示，避免错误宣称旧进程已经清理。

## 已确认事实

现场证据：`data/demo/dispatch-spacenet8/mapgis-810af6d8-00cf-4334-bbc2-e1c6e6fac3f5/network-build.json`。
该次创建数据库成功，道路线类 ID 为 4，20 条道路写入成功，投影接口未报失败；`NetCls.create` 返回 0。
宿主 desktop.log 显示开发授权验证成功。不能把本次建网失败归因于缺少授权文件。
DS_Service.log 未给出这次网络创建失败的具体原因。

## 本轮改动及边界

- 投影后关闭、重新打开道路类，核对持久化数量、空间参考、重算范围与既有网络归属。
- 建网前关闭输入道路类，按官方 CreateNetclsDialog 的类 ID 调用方式避免继续持有输入句柄。句柄占用只是待验证假设，不是已证实根因。
- 保留创建时的类 ID 供后续子边映射使用，不从已关闭的类读取 ID。
- 新增投影返回值、实际 WKT、范围、关闭状态、建网参数与原生返回值的诊断记录。
- 建网成功或失败后，界面结果框显示完整 JSON，不再仅依赖被截断的状态文字。
- 不修改授权，不以第三方路网算法替代原生建网；保留所有失败数据库供排查。

## 验证状态

MapGIS SDK 编译及打包成功；现有 Java 单元测试 40 项通过。单元测试不覆盖已授权宿主内的 JNI 建网，不能据此宣布原生建网修复成功。
独立构建目录：`runtime/network-lifecycle-build`。尚未替换正在运行的宿主插件。
保存并关闭 MapGIS 后，在项目根目录执行 `scripts/build_mapgis_plugin.ps1`，再按现有管理员启动流程执行 `scripts/start_demo.ps1`。
下一次在授权宿主内运行“创建演练路网”后，检查新增证据；仅在节点、边及所有道路子边映射通过后才会标记 `native_network_created=true`。
分钟权、资源绑定、路线验收仍需独立验证；`dispatch_ready` 保持 false。
