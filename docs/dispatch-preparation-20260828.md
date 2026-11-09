# 演练路网调度准备进度

## 2026-08-29 权重部分为空的修正

mapgis-43689678-0b79-48ee-a04d-e089f9330862 现场显示权重ID9和绑定ID10持久化，第1边返回正确Double 64.445...，后续边至少一项返回null。结论：事后appendWeight/appendWeightFld没有为全部已存在边构建权值。

已改为官方CreateNetclsDialog流程：在NetCls.create前建立NetWeightList（fg_length_metres，比例权，double，ID1）与NetWeightFldList（道路类mpLength），随网络拓扑一次创建。准备阶段只读回建网时创建的权及唯一字段绑定，不再追加。失败证据增加具体edge ID、返回类型/值及期望米数。原生路径门禁继续保留。

2026-08-29 现场读回表明 ratioType 仅返回比例系数 1.0，不是 mpLength 的米数。已改为 absoluteType，并按“道路类 ID + 权名/ID”精确核验字段绑定，不再假定全网权字段列表只有一项。

2026-08-29 endpoint-v2 现场验证已得到 24→25 的原生基准路线（边 16，0.2205516 km）。封闭唯一通路后，当前 SDK 返回一个空 PathInfo 表示不可达；路由器现仅在存在障碍边时将该形态解释为无路径，非封路请求或非空端点异常仍会拒绝验收。

## 2026-08-29 15:36 原生闪退根因与保护

hs_err_pid15268.log确认EXCEPTION_ACCESS_VIOLATION发生在NetAnalyseNative.jni_setNetAnalyOption。此前dispatch-preparation已经报“source class数量不等于1”，字段绑定未完成，但构建器错误地继续调用演练路由，导致原生空指针访问。

修正：权重绑定不再依赖不可靠的getSFClsIDLst枚举，直接使用构建阶段已验证的roadClassId；若权重注册、字段绑定、元数据同步、按名称重开或逐边读回任一步失败，则完全跳过NetAnalyse，保存exercise_dispatch_skipped并保持宿主运行。新增门禁回归测试。该修正确保已知失败路径不再进入JNI，但第三方SDK仍可能存在其他进程级缺陷，不能承诺任何原生调用绝不会崩溃。

## 最新修正：注册长度网络权，不再使用默认边长

现场 mapgis-9807c646-d186-419f-b09b-12102f44da2 确认：mpLength 20条均为合理米制长度，端点资源/目的地4项均0米吸附；MapGIS NetCls.getEdgeLength 却固定返回1。因此数据、投影及端点绑定已排除，剩余问题是默认网络边长不可作为本版本SDK的米制阻抗。

现注册比例网络权 fg_length_metres，绑定唯一源线类的 mpLength，执行 syncMetadata，并通过新句柄按名称取得持久化权ID、逐边 getWeightValue。只有注册权与原生边几何长度一致才通过。演练路径改为 userDefine，正反向均使用 fg_length_metres；路径权还必须等于逐边注册权之和，时间再按明确的假设速度换算。默认 getEdgeLength=1仅写诊断，不再用于距离、时间或路线选择。

本轮仅完成代码及SDK编译验证；注册权的JNI读回和路径仍须在授权宿主新建数据库验证。旧数据库没有该网络权，不能用于本轮验证。

## 本轮修正：长度字段与独立端点演练

对照官方 CreateDataDialog / GISDefaultValues，原实现遗漏 mpLength 字段。现为新道路类创建 mpLength 双精度字段，投影后由 MapGIS lengthToField(false, index) 写入平面长度，再将每条属性长度与原生 GeoLine.calLength 对比。后续网络边长交叉校验仍保留。这修正了字段遗漏，但尚未在授权宿主验证 getEdgeLength 全1问题是否消除。

原资源生成器选择道路内部顶点，而端点建网不保证这些顶点为网络节点。新增 --endpoint-staging 选项生成独立目录 data/demo/dispatch-spacenet8-endpoint-v2，三个虚构车辆共同位于道路起点，目的地为终点。原台账、道路几何、失败证据不覆盖，25米阈值不扩大。此场景只验证端点集结，不宣称修复任意位置资源接入。

本轮 MapGIS SDK 编译通过，数据生成测试3项通过。独立包 runtime/network-length-field-build。现场需先停止旧服务、更新插件、重启，再选择新端点目录；不应继续用原内部顶点台账期待同样的节点吸附成功。

## 最新现场：吸附失败及边长异常

现场 ffedcd9b-d5b9-42ed-99cd-06864534c944：拓扑通过；第一辆车绑定节点24、距离0；第二辆车吸附超过25米。旧证据未记录失败距离及坐标，因此不能断言是台账位置问题还是原生查询结果问题。不得直接放宽阈值。

另外，20条边均得到0.002分钟（30km/h对应1米）。此前 minute_defaults_verified 只验证写入读回，不能作为真实边长及时间正确的证明。新增原生 getEdgePos + GeoVarLine.calLength 交叉检查，全部边长校验后才写权；路径报告也执行同一检查，不静默使用可疑长度。吸附失败现在记录资源ID、原生节点、双方投影坐标、距离和accepted=false。

本轮 SDK 编译通过，新增3项长度校验测试。独立包 runtime/network-length-audit-build。根因尚未通过原生几何读回核实；本轮为校验与诊断加固，不能宣称已经解决吸附或长度异常。旧拓扑数据库未改，现场新检查尚未执行。

## 最新实现：资源绑定及封路验收链

新增 MapGisExerciseDispatch，在新建演练网络上只读执行：验证 resources.json、scenario.json、roads.geojson 的 manifest SHA256；使用投影后道路对应顶点通过原生 getNearNod 绑定资源及目的地，最大吸附距离 25 米。原生顶点数量变化时拒绝按索引绑定。吸附偏移被记录，不计入预计行程时间，不能代表真实场站接驳。

演练路由显式选择 MapGIS systemMode_MinDis，原生最短距离路径按统一假设车速计算时间。这不是命名分钟权路由替代品；正式 DispatchPanel 仍保留命名权路径。演练执行基线容量分配、源道路封闭到原生边映射、封闭后重算。必须有非零基线路径，封闭必须命中基线路径，返回路径不能包含阻断边；缺少条件或原生返回不完整即拒绝验收。

输出 exercise-dispatch.json 及转义后的 exercise-dispatch.html。主界面显示绑定/封路验收结果，不将业务失败误报为拓扑失败。即使演练通过，dispatch_ready 仍为 false，只有 exercise_routes_verified 可以为 true。

SDK 编译和 49 项单元测试通过；本轮尚未在授权宿主执行新增 JNI 路径。独立构建目录 runtime/exercise-dispatch-build。历史成功数据库及运行中插件未改。下一步需现场验证；25 米内无节点、顶点改变、没有非零基线路径等都可能是需要调整数据或绑定方案的真实阻塞，不能通过扩大阈值或假造节点掩盖。

现场已通过的路网：`data/demo/dispatch-spacenet8/mapgis-749e7d61-1ded-47f5-beaa-f8a8d66a86ea/network-build.json`，20 条边、28 个节点、20 条源道路全部映射。该历史数据库未被本轮修改。

本轮新增：仅在新演练路网创建成功后，从 scenario.json 读取明确标为假设的速度，用 MapGIS 原生边长（UTM 米）计算分钟数，写入双向缺省权及零节点延迟。使用另一个原生句柄读回验证，记录到 dispatch-preparation.json。失败不再否定先前已通过的拓扑结果，dispatch_ready 始终保持 false。

限制：缺省权不等于现有 MapGisNetworkRouter 要求的命名权。尚未接通命名权、原生资源节点绑定、基线/阻断路径对比及容量分配的端到端验收，不能将该准备记录作为可执行 DispatchRequest，也不能代表实际车速或实际救援资源。

编译及 47 项 Java 测试通过；测试中的三项新检查覆盖单位换算与非法值，不包含原生写权运行。新插件独立构建目录 runtime/dispatch-preparation-build，运行中的旧插件未替换。资源、路径及原生写权仍需进一步实现或现场验证。
