package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.RoadImpedance;
import com.mapgis.floodguard.business.RoadNetworkMappingAudit;
import com.zondy.mapgis.att.Record;
import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.controls.SelectItem;
import com.zondy.mapgis.geodatabase.SFeatureCls;
import com.zondy.mapgis.geodatabase.QueryDef;
import com.zondy.mapgis.geodatabase.RecordSet;
import com.zondy.mapgis.geodatabase.net.ElemType;
import com.zondy.mapgis.geodatabase.net.NetCls;
import com.zondy.mapgis.geometry.Dot;
import com.zondy.mapgis.geometry.Geometry;
import com.zondy.mapgis.geometry.GeometryOperator;
import com.zondy.mapgis.map.MapLayer;
import com.zondy.mapgis.map.VectorLayer;
import javafx.animation.KeyFrame;
import javafx.animation.Timeline;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.input.MouseButton;
import javafx.scene.input.MouseEvent;
import javafx.scene.layout.*;
import javafx.stage.FileChooser;
import javafx.util.Duration;
import java.nio.file.*;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.*;
import java.util.function.Consumer;

/** Native MapGIS route, resource and drill GUI. */
public final class EmergencyDispatchPanel extends VBox implements AutoCloseable {
    private final MapControl control;
    private final Path evidenceRoot;
    private final Consumer<String> log;
    private final Consumer<EmergencyRoutePlanner.Result> routeCompleted;
    private final Runnable capture;
    private final ObjectMapper json=new ObjectMapper();
    private final ComboBox<MapLayer> networkChoice=new ComboBox<>();
    private final ComboBox<ResourceManager.Resource> startChoice=new ComboBox<>(), targetChoice=new ComboBox<>();
    private final TextField speed=new TextField("30");
    private final Label status=new Label("加载原生 MapGIS 路网、道路状态证据和资源点后规划路线。");
    private final TextArea details=new TextArea("点击路线、风险道路或资源点查询属性。");
    private final ListView<ResourceManager.Resource> inventory=new ListView<>();
    private final TextField id=new TextField(), name=new TextField(), type=new TextField(), state=new TextField("AVAILABLE");
    private final TextField capacity=new TextField("1"), current=new TextField("0"), x=new TextField(), y=new TextField();
    private final ComboBox<ResourceManager.Kind> kind=new ComboBox<>();
    private final TextArea recommendations=new TextArea();
    private final Label simulationStatus=new Label("未开始模拟");
    private final Label incidentStatus=new Label("未选灾害区域；可在风险专题图上点击区域。");
    private final List<String> simulationLog=new ArrayList<>();
    private final Map<Integer,RoadImpedance.Status> roadStatuses=new LinkedHashMap<>();
    private ResourceManager resources;
    private EmergencyRoutePlanner.Result route;
    private MapGisRouteThematicWriter.Result thematic;
    private List<VectorLayer> routeLayers=List.of();
    private Path reportDirectory;
    private Path roadLedger;
    private Path mappingAuditPath;
    private String ledgerNetworkFingerprint,roadLedgerSha256;
    private Timeline timeline;
    private String simulationMarkerId;
    private String plannedStartId,plannedTargetId;
    private boolean refreshingNetwork;
    private int incidentNode=-1;
    private String incidentArea;
    private String incidentRisk;

    public EmergencyDispatchPanel(MapControl control,Path evidenceRoot,Consumer<String> log,
                                  Consumer<EmergencyRoutePlanner.Result> routeCompleted,Runnable capture) {
        this.control=control; this.evidenceRoot=evidenceRoot; this.log=log; this.routeCompleted=routeCompleted; this.capture=capture;
        setPadding(new Insets(12)); setSpacing(8);
        Label title=new Label("应急调度 · MapGIS 原生路径与空间资源"); title.setStyle("-fx-font-size:18px;-fx-font-weight:bold;");
        networkChoice.setPrefWidth(420); networkChoice.setCellFactory(v->networkCell()); networkChoice.setButtonCell(networkCell());
        networkChoice.valueProperty().addListener((o,oldLayer,newLayer)->{
            if (!refreshingNetwork && oldLayer!=newLayer) { clearRouteView(); roadLedger=null; ledgerNetworkFingerprint=null; roadStatuses.clear();
                incidentNode=-1; incidentArea=null; incidentRisk=null;
                incidentStatus.setText("未选灾害区域；可在风险专题图上点击区域。"); }
        });
        Button refresh=button("刷新路网与资源",this::refresh);
        HBox common=new HBox(8,new Label("原生路网"),networkChoice,refresh,button("导出路网指纹",this::exportNetworkFingerprint));
        TabPane tabs=new TabPane(new Tab("路径规划",routeTab()),new Tab("资源管理",resourceTab()),new Tab("救援模拟",simulationTab()));
        tabs.getTabs().forEach(t->t.setClosable(false));
        status.setWrapText(true); details.setEditable(false); details.setPrefRowCount(6);
        getChildren().addAll(title,common,tabs,status,new Label("地图对象属性"),details);
        control.addEventFilter(MouseEvent.MOUSE_CLICKED,e->{ if (e.getButton()==MouseButton.PRIMARY) inspect(e); });
        refresh();
    }
    private static ListCell<MapLayer> networkCell() {
        return new ListCell<>() { @Override protected void updateItem(MapLayer layer,boolean empty) {
            super.updateItem(layer,empty); setText(empty||layer==null?"—":layer.getName()+" · "+layer.getURL());
        }};
    }
    private static ListCell<ResourceManager.Resource> resourceCell() {
        return new ListCell<>() { @Override protected void updateItem(ResourceManager.Resource item,boolean empty) {
            super.updateItem(item,empty); setText(empty||item==null?"—":item.name()+" ["+item.id()+"]");
        }};
    }
    @FunctionalInterface private interface Action { void run() throws Exception; }
    private Button button(String label,Action task) {
        Button button=new Button(label); button.setOnAction(e->{ try { task.run(); }
            catch (Exception | LinkageError error) { fail(label,error); } }); return button;
    }
    private VBox routeTab() {
        startChoice.setPrefWidth(210); targetChoice.setPrefWidth(210);
        startChoice.setCellFactory(v->resourceCell()); startChoice.setButtonCell(resourceCell());
        targetChoice.setCellFactory(v->resourceCell()); targetChoice.setButtonCell(resourceCell());
        speed.setPrefWidth(70);
        VBox box=new VBox(8,new HBox(8,button("加载道路状态证据",this::loadRoadLedger),
                        button("封路前后规划",this::planRoute),button("自动推荐资源",this::recommend)),
                new HBox(8,new Label("车辆"),startChoice,new Label("目的地"),targetChoice,
                        new Label("演练速度 km/h"),speed),
                incidentStatus,
                new Label("道路状态须能映射到当前 MapGIS 原生路网；阻断边使用原生路障排除。"),
                new Label("资源匹配结果"),recommendations);
        recommendations.setEditable(false); recommendations.setPrefRowCount(5); box.setSpacing(8); return box;
    }
    private VBox resourceTab() {
        kind.getItems().setAll(ResourceManager.Kind.values()); kind.setValue(ResourceManager.Kind.VEHICLE);
        inventory.setCellFactory(v->resourceCell()); inventory.setPrefHeight(145);
        inventory.getSelectionModel().selectedItemProperty().addListener((o,a,b)->{ if (b!=null) fill(b); });
        GridPane grid=new GridPane(); grid.setHgap(6); grid.setVgap(5);
        Object[][] fields={{"类别",kind},{"编号",id},{"名称",name},{"类型",type},{"状态",state},
                {"总容量",capacity},{"当前占用",current},{"X (投影米)",x},{"Y (投影米)",y}};
        for (int i=0;i<fields.length;i++) { grid.add(new Label((String)fields[i][0]),i%3*2,i/3);
            grid.add((javafx.scene.Node)fields[i][1],i%3*2+1,i/3); }
        return new VBox(8,new HBox(8,button("创建 MapGIS 资源图层",this::createResources),
                button("打开已有资源库",this::openResources),
                button("添加资源点",this::addResource),button("修改属性/位置",this::updateResource),
                button("删除资源点",this::deleteResource)),grid,inventory);
    }
    private VBox simulationTab() {
        simulationStatus.setWrapText(true);
        return new VBox(8,new HBox(8,button("开始救援模拟",this::startSimulation),button("停止模拟",this::stopSimulation)),
                new Label("模拟标记沿 MapGIS 路网节点移动；不会下发实际救援指令。"),simulationStatus);
    }
    public void refresh() {
        MapLayer prior=networkChoice.getValue(); List<MapLayer> networks=new ArrayList<>();
        for (int i=0;i<control.getMap().getLayerCount();i++) {
            MapLayer layer=control.getMap().getLayer(i);
            if (layer.getData() instanceof NetCls net && net.hasOpened()) networks.add(layer);
        }
        refreshingNetwork=true;
        try {
            networkChoice.getItems().setAll(networks);
            if (prior!=null && networks.contains(prior)) networkChoice.setValue(prior);
            else if (networks.size()==1) networkChoice.setValue(networks.get(0));
        } finally { refreshingNetwork=false; }
        if (prior!=null && prior!=networkChoice.getValue()) {
            clearRouteView(); roadLedger=null; ledgerNetworkFingerprint=null; roadStatuses.clear(); incidentNode=-1;
            incidentArea=null; incidentRisk=null; incidentStatus.setText("未选灾害区域；可在风险专题图上点击区域。");
        }
        refreshResources();
    }
    public Path latestRouteReport() { return reportDirectory==null?null:reportDirectory.resolve("route_report.json"); }
    public Path latestRecommendations() { return reportDirectory==null?null:reportDirectory.resolve("resource-recommendations.json"); }
    public int availableResourceCount() { return resources==null?0:(int)resources.list().stream().filter(r->"AVAILABLE".equalsIgnoreCase(r.status())).count(); }
    public void loadScenarioResources(Path manifest) throws Exception {
        if (resources!=null) throw new IllegalStateException("本次会话已有 MapGIS 资源库");
        NetCls net=network(); resources=ResourceManager.openExisting(control,manifest,networkChoice.getValue().getSrefInfo(),net);
        refreshResources(); networkChoice.setDisable(true); log.accept("已加载案例资源库："+manifest);
    }
    public Path loadScenarioRoadStatuses(Path file) throws Exception {
        loadRoadLedger(file);
        Path directory=Files.createDirectories(evidenceRoot.resolve("closure-"+UUID.randomUUID()));
        var displayed=new MapGisRouteThematicWriter().write(control,network(),networkChoice.getValue().getSrefInfo(),
                null,roadStatuses,directory);
        routeLayers=displayed.layers();
        log.accept("MapGIS 已生成封路专题图："+displayed.manifest());
        return displayed.manifest();
    }
    public Path planScenarioRoute(String startId,String targetId,double speedKph) throws Exception {
        refresh(); speed.setText(Double.toString(speedKph));
        startChoice.getItems().stream().filter(r->r.id().equals(startId)).findFirst().ifPresent(startChoice::setValue);
        targetChoice.getItems().stream().filter(r->r.id().equals(targetId)).findFirst().ifPresent(targetChoice::setValue);
        if (startChoice.getValue()==null || targetChoice.getValue()==null) throw new IllegalArgumentException("案例车辆或目标编号不在 MapGIS 资源库");
        planRoute(); return latestRouteReport();
    }
    public Path recommendScenarioResources() throws Exception { recommend(); return latestRecommendations(); }
    private NetCls network() {
        MapLayer layer=networkChoice.getValue();
        if (layer==null || !(layer.getData() instanceof NetCls net) || !net.hasOpened())
            throw new IllegalStateException("请先从数据管理加载并选择 MapGIS 原生路网");
        String wkt=layer.getSrefInfo()==null?"":layer.getSrefInfo().toWkt().toLowerCase(Locale.ROOT);
        if (!wkt.startsWith("projcs[") || !(wkt.contains("unit[\"metre\",1") || wkt.contains("unit[\"meter\",1")))
            throw new IllegalArgumentException("路线测量要求米制投影路网");
        return net;
    }
    private void exportNetworkFingerprint() throws Exception {
        NetCls net=network();
        Map<String,Object> evidence=new LinkedHashMap<>();
        evidence.put("network_url",net.getURL());
        evidence.put("network_fingerprint_sha256",MapGisNetworkFingerprint.calculate(net));
        evidence.put("network_node_count",net.getNodCount());
        evidence.put("network_edge_count",net.getEdgeCount());
        evidence.put("captured_at",LocalDateTime.now().toString());
        evidence.put("verification","NATIVE_NETWORK_INVENTORY_ONLY");
        Path file=Files.createDirectories(evidenceRoot).resolve("network-inventory-"+UUID.randomUUID()+".json");
        Files.writeString(file,json.writerWithDefaultPrettyPrinter().writeValueAsString(evidence),StandardOpenOption.CREATE_NEW);
        status.setText("已导出当前 MapGIS 路网指纹："+file); log.accept(status.getText());
    }
    private void createResources() throws Exception {
        if (resources!=null) throw new IllegalStateException("本次会话已有 MapGIS 资源库");
        network(); resources=new ResourceManager(control,networkChoice.getValue().getSrefInfo(),evidenceRoot);
        networkChoice.setDisable(true);
        status.setText("MapGIS 资源点图层已创建："+resources.databasePath());
        log.accept("资源空间库已创建："+resources.databasePath()); refreshResources(); capture.run();
    }
    private void openResources() throws Exception {
        if (resources!=null) throw new IllegalStateException("本次会话已有 MapGIS 资源库");
        FileChooser chooser=new FileChooser(); chooser.setTitle("选择 resource-manifest.json");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("JSON","*.json"));
        var file=chooser.showOpenDialog(getScene().getWindow()); if (file==null) return;
        NetCls net=network(); resources=ResourceManager.openExisting(control,file.toPath(),networkChoice.getValue().getSrefInfo(),net);
        refreshResources();
        networkChoice.setDisable(true);
        status.setText("已打开 MapGIS 资源库："+resources.databasePath()); log.accept(status.getText()); capture.run();
    }
    private ResourceManager manager() {
        if (resources==null) throw new IllegalStateException("请先创建 MapGIS 资源图层"); return resources;
    }
    private ResourceManager.Resource fromForm() {
        NetCls net=network(); double px=Double.parseDouble(x.getText().trim()),py=Double.parseDouble(y.getText().trim());
        Dot location=new Dot(px,py); int node=Math.toIntExact(net.getNearNod(location,25));
        if (node<=0) throw new IllegalArgumentException("资源位置距离 MapGIS 路网节点超过 25 m");
        Dot snapped=new Dot(); if (net.getNodPos(node,snapped)<=0 || Math.hypot(px-snapped.getX(),py-snapped.getY())>25)
            throw new IllegalArgumentException("资源位置无法在 25 m 内绑定原生路网节点");
        return new ResourceManager.Resource(id.getText().trim(),kind.getValue(),name.getText().trim(),type.getText().trim(),
                state.getText().trim(),Integer.parseInt(capacity.getText().trim()),Integer.parseInt(current.getText().trim()),px,py,node);
    }
    private void addResource() { manager().add(fromForm()); refreshResources(); log.accept("MapGIS 已添加资源点："+id.getText()); capture.run(); }
    private void updateResource() { manager().update(fromForm()); clearRouteView(); refreshResources(); log.accept("MapGIS 已更新资源点："+id.getText()); capture.run(); }
    private void deleteResource() {
        String key=id.getText().trim(); manager().delete(key); clearRouteView(); refreshResources();
        log.accept("MapGIS 已删除资源点："+key); capture.run();
    }
    private void refreshResources() {
        if (resources==null) return;
        List<ResourceManager.Resource> all=resources.list(); inventory.getItems().setAll(all);
        startChoice.getItems().setAll(all.stream().filter(r->r.kind()==ResourceManager.Kind.VEHICLE).toList());
        targetChoice.getItems().setAll(all.stream().filter(r->r.kind()!=ResourceManager.Kind.VEHICLE).toList());
    }
    private static void validateResources(NetCls net,List<ResourceManager.Resource> entries) {
        for (var resource:entries) {
            Dot node=new Dot();
            if (net.getNodeInfo(resource.nodeId())==null || net.getNodPos(resource.nodeId(),node)<=0
                    || Math.hypot(resource.x()-node.getX(),resource.y()-node.getY())>25)
                throw new IllegalArgumentException("资源节点绑定不属于当前路网或距离超过 25 m："+resource.id());
        }
    }
    private void fill(ResourceManager.Resource item) {
        kind.setValue(item.kind()); id.setText(item.id()); name.setText(item.name()); type.setText(item.type());
        state.setText(item.status()); capacity.setText(Integer.toString(item.capacity()));
        current.setText(Integer.toString(item.current())); x.setText(Double.toString(item.x())); y.setText(Double.toString(item.y()));
    }
    private void loadRoadLedger() throws Exception {
        FileChooser chooser=new FileChooser(); chooser.setTitle("选择道路灾损状态与核查证据 JSON");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("JSON","*.json"));
        var file=chooser.showOpenDialog(getScene().getWindow()); if (file==null) return;
        loadRoadLedger(file.toPath());
    }
    private void loadRoadLedger(Path file) throws Exception {
        NetCls net=network();
        if (Files.size(file)>5_000_000) throw new IllegalArgumentException("道路状态文件过大");
        JsonNode root=json.readTree(file.toFile());
        String actualFingerprint=MapGisNetworkFingerprint.calculate(net);
        if (!actualFingerprint.equals(root.path("network_fingerprint_sha256").asText()))
            throw new IllegalArgumentException("道路状态缺少当前 MapGIS 路网指纹，或路网已重建；请重新核查映射");
        if (!net.getURL().equals(root.path("network_url").asText())) throw new IllegalArgumentException("道路状态与当前路网 URL 不一致");
        if (!"NORMAL".equals(root.path("unlisted_status").asText())
                || root.path("unlisted_evidence").asText().isBlank()
                || root.path("network_edge_count").asLong(-1)!=net.getEdgeCount())
            throw new IllegalArgumentException("未逐条列出的路网边必须有全网正常状态核查依据及匹配的边总数");
        String sourceUrl=root.path("roads_url").asText();
        SFeatureCls roads=null;
        for (int i=0;i<control.getMap().getLayerCount();i++) {
            MapLayer layer=control.getMap().getLayer(i);
            if (layer instanceof VectorLayer vector && vector.getData() instanceof SFeatureCls cls && sourceUrl.equals(cls.getURL())) roads=cls;
        }
        if (roads==null) throw new IllegalArgumentException("请加载当前网络的原始道路 MapGIS 要素类："+sourceUrl);
        var mapper=new MapGisRoadNetworkMapper(net,roads,sourceUrl);
        if (!root.path("roads").isArray()) throw new IllegalArgumentException("缺少 roads 数组");
        QueryDef query=new QueryDef(); RecordSet rows=null; int sourceCount; Set<String> sourceIds=new LinkedHashSet<>();
        try { rows=roads.query(query); if (rows==null) throw new IllegalStateException("无法枚举原始道路");
            sourceCount=rows.getCount();
            if (sourceCount<0 || sourceCount>200_000) throw new IllegalStateException("原始道路数量超出交互审计上限");
            if (sourceCount>0) rows.moveFirst();
            for (int i=0;i<sourceCount;i++) {
                if (!sourceIds.add(Long.toString(rows.getID()))) throw new IllegalStateException("原始道路 OID 重复");
                if (i+1<sourceCount) rows.moveNext();
            }
        }
        finally { if (rows!=null) rows.dispose(); query.dispose(); }
        if (sourceCount<=0 || root.path("source_road_count").asInt(-1)!=sourceCount)
            throw new IllegalArgumentException("道路状态与当前原始道路要素数量不一致");
        List<RoadNetworkMappingAudit.Entry> entries=new ArrayList<>(); Set<String> listed=new HashSet<>();
        for (JsonNode item:root.path("roads")) {
            String featureId=item.path("source_feature_id").asText();
            RoadImpedance.Status roadStatus=RoadImpedance.Status.valueOf(item.path("status").asText());
            entries.add(new RoadNetworkMappingAudit.Entry(featureId,roadStatus,item.path("evidence").asText()));
            listed.add(featureId);
        }
        for (String sourceId:sourceIds) if (!listed.contains(sourceId))
            entries.add(new RoadNetworkMappingAudit.Entry(sourceId,RoadImpedance.Status.NORMAL,
                    root.path("unlisted_evidence").asText()));
        long[] ids=net.queryID(0,ElemType.egdeElemType); Set<Integer> known=new HashSet<>();
        if (ids==null) throw new IllegalStateException("无法枚举当前路网边");
        for (long edge:ids) known.add(Math.toIntExact(edge));
        var audit=RoadNetworkMappingAudit.check(root.path("network_fingerprint_sha256").asText(),actualFingerprint,
                sourceCount,entries,known,mapper,sourceUrl);
        Path auditFile=Files.createDirectories(evidenceRoot).resolve("road-mapping-audit-"+UUID.randomUUID()+".json");
        Map<String,Object> mappingEvidence=new LinkedHashMap<>();
        mappingEvidence.put("roads_url",sourceUrl); mappingEvidence.put("network_url",net.getURL());
        mappingEvidence.put("network_fingerprint_sha256",actualFingerprint);
        mappingEvidence.put("source_road_count",audit.sourceRoadCount());
        mappingEvidence.put("mapped_road_count",audit.mappedRoadCount());
        mappingEvidence.put("unmapped_road_count",audit.unmappedRoadCount());
        mappingEvidence.put("duplicate_mapping_count",audit.duplicateMappingCount());
        mappingEvidence.put("missing_edge_count",audit.missingEdgeCount());
        mappingEvidence.put("ledger_mismatch_count",audit.ledgerMismatchCount());
        mappingEvidence.put("ambiguous_count",audit.ambiguousCount());
        mappingEvidence.put("status",audit.status()); mappingEvidence.put("issues",audit.issues());
        Files.writeString(auditFile,json.writerWithDefaultPrettyPrinter().writeValueAsString(mappingEvidence),
                StandardOpenOption.CREATE_NEW);
        if (!audit.routable()) throw new IllegalArgumentException("道路映射未通过："+audit.status()+" "+audit.issues());
        clearRouteView(); roadStatuses.clear(); roadStatuses.putAll(audit.edgeStatuses()); roadLedger=file;
        mappingAuditPath=auditFile;
        ledgerNetworkFingerprint=actualFingerprint;
        roadLedgerSha256=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(file)));
        status.setText("已核查并映射 "+audit.mappedRoadCount()+" 条源道路、"+roadStatuses.size()+" 条 MapGIS 网络边；来源："+roadLedger);
        log.accept("道路状态证据已载入："+roadLedger);
        if (resources!=null && startChoice.getValue()!=null && targetChoice.getValue()!=null) planRoute();
    }
    private double speed() { return Double.parseDouble(speed.getText().trim()); }
    private void planRoute() throws Exception {
        NetCls net=network(); ResourceManager.Resource start=startChoice.getValue(),target=targetChoice.getValue();
        if (start==null || target==null) throw new IllegalArgumentException("选择车辆和医疗点/避难点");
        if (!"AVAILABLE".equalsIgnoreCase(start.status())) throw new IllegalArgumentException("车辆当前不可用");
        if (target.kind()==ResourceManager.Kind.SHELTER && target.current()>=target.capacity())
            throw new IllegalArgumentException("避难点容量已满");
        if (roadLedger==null) throw new IllegalStateException("必须加载经源道路要素映射的灾损状态证据");
        if (!MapGisNetworkFingerprint.calculate(net).equals(ledgerNetworkFingerprint)) {
            clearRouteView(); throw new IllegalStateException("当前路网已变化，请重新加载道路状态并复核边映射");
        }
        validateResources(net,manager().list());
        clearRouteView();
        var planner=new EmergencyRoutePlanner();
        var planned=incidentNode>0
                ? combine(planner.plan(net,start.nodeId(),incidentNode,Map.copyOf(roadStatuses),speed()),
                          planner.plan(net,incidentNode,target.nodeId(),Map.copyOf(roadStatuses),speed()))
                : planner.plan(net,start.nodeId(),target.nodeId(),Map.copyOf(roadStatuses),speed());
        Path directory=Files.createDirectories(evidenceRoot.resolve("route-"+UUID.randomUUID()));
        var displayed=new MapGisRouteThematicWriter().write(control,net,networkChoice.getValue().getSrefInfo(),planned,
                roadStatuses,directory);
        try {
            int blockedRemoved=(int)planned.original().edges().stream().filter(planned.blockedEdges()::contains).count();
            Map<String,Object> report=new LinkedHashMap<>();
            report.put("start",start.name()); report.put("target",target.name());
            report.put("distance",planned.optimized().distanceMetres()); report.put("time",planned.optimized().estimatedMinutes());
            report.put("dynamic_cost_metres",planned.optimized().impedanceMetres());
            report.put("risk_level",planned.optimized().riskLevel()); report.put("blocked_roads_removed",blockedRemoved);
            report.put("road_count",planned.optimized().edges().size()); report.put("dangerous_roads_avoided",planned.dangerousEdgesAvoided());
            report.put("original",planned.original()); report.put("optimized",planned.optimized());
            report.put("network_url",net.getURL()); report.put("network_fingerprint_sha256",ledgerNetworkFingerprint);
            report.put("road_status_evidence",roadLedger.toString()); report.put("road_status_sha256",roadLedgerSha256);
            report.put("road_mapping_audit",mappingAuditPath.toString());
            report.put("calculation_engine","MapGIS NetAnalyse + NetBarrier");
            report.put("impedance_unit","metres multiplied by road status factor");
            report.put("resource_database",manager().databasePath().toString()); report.put("thematic_manifest",displayed.manifest().toString());
            report.put("incident_area",incidentArea); report.put("incident_risk_level",incidentRisk);
            report.put("assumed_speed_kph",speed()); report.put("time_is_estimate",true);
            Files.writeString(directory.resolve("route_report.json"),json.writerWithDefaultPrettyPrinter().writeValueAsString(report),StandardOpenOption.CREATE_NEW);
        } catch (Exception | LinkageError error) {
            for (VectorLayer layer:displayed.layers()) control.getMap().remove(layer);
            control.refreshWnd(); throw error;
        }
        routeLayers=displayed.layers(); thematic=displayed; route=planned; reportDirectory=directory;
        plannedStartId=start.id(); plannedTargetId=target.id();
        routeCompleted.accept(planned);
        status.setText(String.format(Locale.ROOT,"MapGIS 绕行路线：%.1f m，预计 %.1f 分钟，%d 条道路，风险 %s；已避开 %d 条危险边。报告：%s",
                planned.optimized().distanceMetres(),planned.optimized().estimatedMinutes(),planned.optimized().edges().size(),
                planned.optimized().riskLevel(),planned.dangerousEdgesAvoided(),directory.resolve("route_report.json")));
        log.accept(status.getText()); capture.run();
    }
    private void recommend() throws Exception {
        NetCls net=network(); ResourceManager.Resource target=targetChoice.getValue();
        if (target==null || roadLedger==null) throw new IllegalArgumentException("先选择目标并加载道路状态");
        if (!MapGisNetworkFingerprint.calculate(net).equals(ledgerNetworkFingerprint)) {
            clearRouteView(); throw new IllegalStateException("路网已变化，请重新核查道路状态");
        }
        validateResources(net,manager().list());
        List<String> lines=new ArrayList<>();
        List<Map<String,Object>> evaluated=new ArrayList<>();
        for (ResourceManager.Kind category:ResourceManager.Kind.values()) {
            List<ResourceManager.Resource> candidates=manager().list().stream().filter(r->r.kind()==category)
                    .filter(r->"AVAILABLE".equalsIgnoreCase(r.status()))
                    .filter(r->category!=ResourceManager.Kind.SHELTER || r.current()<r.capacity())
                    .filter(r->!r.id().equals(target.id())).sorted(Comparator.comparing(ResourceManager.Resource::id)).toList();
            ResourceManager.Resource best=null; EmergencyRoutePlanner.Route bestRoute=null;
            for (var candidate:candidates) {
                try {
                    int origin=category!=ResourceManager.Kind.VEHICLE && incidentNode>0?incidentNode:candidate.nodeId();
                    int endpoint=category!=ResourceManager.Kind.VEHICLE && incidentNode>0?candidate.nodeId():
                            incidentNode>0?incidentNode:target.nodeId();
                    var candidateRoute=new EmergencyRoutePlanner().plan(net,origin,endpoint,roadStatuses,speed()).optimized();
                    Map<String,Object> row=new LinkedHashMap<>(); row.put("resource_id",candidate.id());
                    row.put("kind",category.name()); row.put("status","REACHABLE");
                    row.put("distance_metres",candidateRoute.distanceMetres());
                    row.put("dynamic_cost_metres",candidateRoute.impedanceMetres());
                    row.put("estimated_minutes",candidateRoute.estimatedMinutes()); evaluated.add(row);
                    if (bestRoute==null || candidateRoute.impedanceMetres()<bestRoute.impedanceMetres()
                            || (candidateRoute.impedanceMetres()==bestRoute.impedanceMetres()
                                && (candidateRoute.distanceMetres()<bestRoute.distanceMetres()
                                    || (candidateRoute.distanceMetres()==bestRoute.distanceMetres()
                                        && candidate.id().compareTo(best.id())<0)))) {
                        best=candidate; bestRoute=candidateRoute;
                    }
                } catch (IllegalStateException unreachable) {
                    Map<String,Object> row=new LinkedHashMap<>(); row.put("resource_id",candidate.id());
                    row.put("kind",category.name()); row.put("status","UNREACHABLE");
                    row.put("reason",unreachable.getMessage()); evaluated.add(row);
                    log.accept("不可达资源："+candidate.id()+" · "+unreachable.getMessage());
                }
            }
            lines.add(category+"："+(best==null?"无可达可用资源":best.name()+" / 距离 "+String.format(Locale.ROOT,"%.1f",bestRoute.distanceMetres())+
                    " m / 预计 "+String.format(Locale.ROOT,"%.1f",bestRoute.estimatedMinutes())+" min / 风险 "+bestRoute.riskLevel()));
        }
        recommendations.setText((incidentArea==null?"":"灾害区域："+incidentArea+" / "+incidentRisk+"\n")+String.join("\n",lines));
        Path folder=reportDirectory!=null?reportDirectory:Files.createDirectories(evidenceRoot.resolve("recommendation-"+UUID.randomUUID()));
        Path resultFile=folder.resolve("resource-recommendations.json");
        Map<String,Object> result=new LinkedHashMap<>(); result.put("target",target.id());
        result.put("incident_area",incidentArea); result.put("incident_risk_level",incidentRisk);
        result.put("road_status_evidence",roadLedger.toString()); result.put("road_status_sha256",roadLedgerSha256);
        result.put("network_fingerprint_sha256",ledgerNetworkFingerprint);
        result.put("resource_manifest",manager().manifestPath().toString());
        result.put("calculation_engine","MapGIS NetAnalyse + NetBarrier");
        result.put("candidates",evaluated); result.put("recommendations",lines);
        Files.writeString(resultFile,json.writerWithDefaultPrettyPrinter().writeValueAsString(result),
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);
        log.accept("MapGIS 路网资源推荐完成；目标="+target.name()+"；证据="+resultFile);
        capture.run();
    }
    private void startSimulation() {
        if (route==null || reportDirectory==null) throw new IllegalStateException("请先完成原生路径规划");
        if (startChoice.getValue()==null || targetChoice.getValue()==null
                || !startChoice.getValue().id().equals(plannedStartId)
                || !targetChoice.getValue().id().equals(plannedTargetId))
            throw new IllegalStateException("车辆或目标已改变，请重新规划路线");
        stopSimulation();
        NetCls net=network(); var start=startChoice.getValue();
        simulationMarkerId="SIM-"+UUID.randomUUID(); simulationLog.clear();
        simulationLog.add(LocalDateTime.now()+" 演练开始 vehicle="+start.id()+" target="+targetChoice.getValue().id()
                +" report="+latestRouteReport()+"; no dispatch command sent");
        List<Integer> nodes=route.optimized().nodes(); final int[] index={0};
        timeline=new Timeline(new KeyFrame(Duration.millis(650),e->{
            try {
                int node=nodes.get(index[0]); Dot point=new Dot();
                if (net.getNodPos(node,point)<=0) throw new IllegalStateException("MapGIS 无法读取模拟节点："+node);
                var marker=new ResourceManager.Resource(simulationMarkerId,ResourceManager.Kind.VEHICLE,"救援模拟标记","SIMULATION",
                        "SIMULATING",1,0,point.getX(),point.getY(),node);
                if (index[0]==0) manager().add(marker); else manager().update(marker);
                String message=LocalDateTime.now()+" 节点 "+(index[0]+1)+"/"+nodes.size()+" MapGIS node="+node;
                simulationLog.add(message); simulationStatus.setText(message); log.accept("救援模拟："+message);
                if (index[0]==0 || index[0]==nodes.size()/2) capture.run();
                index[0]++;
            } catch (Exception error) { stopSimulation(); fail("救援模拟",error); }
        }));
        timeline.setCycleCount(nodes.size());
        timeline.setOnFinished(e->stopSimulation()); timeline.play();
    }
    private void stopSimulation() {
        if (timeline!=null) { timeline.stop(); timeline=null; }
        if (simulationMarkerId!=null && resources!=null) {
            try { if (resources.find(simulationMarkerId)!=null) resources.delete(simulationMarkerId); }
            catch (Exception error) { log.accept("模拟标记清理失败："+error.getMessage()); }
            simulationMarkerId=null;
        }
        if (!simulationLog.isEmpty() && reportDirectory!=null) {
            try { Files.write(reportDirectory.resolve("rescue-simulation.log"),simulationLog,
                    StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING); }
            catch (Exception error) { log.accept("模拟日志保存失败："+error.getMessage()); }
            simulationStatus.setText("模拟已结束；日志："+reportDirectory.resolve("rescue-simulation.log")); capture.run();
        }
    }
    private void clearRouteView() {
        if (timeline!=null) stopSimulation();
        for (VectorLayer old:routeLayers) control.getMap().remove(old);
        if (!routeLayers.isEmpty()) control.refreshWnd();
        routeLayers=List.of(); route=null; thematic=null; reportDirectory=null;
        recommendations.clear();
        plannedStartId=null; plannedTargetId=null;
    }
    private void inspect(MouseEvent event) {
        try {
            Dot location=control.localToLocation(event.getX(),event.getY()); if (location==null) return;
            for (int j=control.getMap().getLayerCount()-1;j>=0;j--) {
                MapLayer riskLayer=control.getMap().getLayer(j);
                if (!(riskLayer instanceof VectorLayer vector) || !riskLayer.getName().contains("洪涝风险分区")
                        || !(vector.getData() instanceof SFeatureCls cls)) continue;
                List<SelectItem> riskHits=control.identifySelections(location,vector);
                if (riskHits==null || riskHits.isEmpty()) continue;
                Record riskRecord=cls.getAtt(riskHits.get(0).getOid()); Geometry shape=cls.getGeometry(riskHits.get(0).getOid());
                if (riskRecord==null || shape==null) throw new IllegalStateException("风险区属性或几何缺失");
                try {
                    Geometry projected=vector.getSrefInfo().toWkt().equals(networkChoice.getValue().getSrefInfo().toWkt())
                            ? shape.clone() : GeometryOperator.project(shape,vector.getSrefInfo(),networkChoice.getValue().getSrefInfo());
                    if (projected==null) throw new IllegalStateException("MapGIS 风险区投影失败");
                    try {
                        var bounds=projected.calRect(); Dot centre=new Dot((bounds.getXMin()+bounds.getXMax())/2,
                                (bounds.getYMin()+bounds.getYMax())/2);
                        int node=Math.toIntExact(network().getNearNod(centre,500));
                        if (node<=0) throw new IllegalStateException("风险区中心 500 m 内无路网节点；请核对灾害区域与路网");
                        if (node!=incidentNode) clearRouteView();
                        incidentNode=node; incidentArea=String.valueOf(riskRecord.getFieldVal("area_name"));
                        incidentRisk=String.valueOf(riskRecord.getFieldVal("risk_level"));
                        incidentStatus.setText("灾害区域："+incidentArea+" / 风险 "+incidentRisk+" / MapGIS 节点 "+node);
                        details.setText(incidentStatus.getText()); log.accept("已选择灾害区域："+incidentStatus.getText()); capture.run();
                    } finally { projected.dispose(); }
                } finally { riskRecord.dispose(); shape.dispose(); }
                return;
            }
            List<VectorLayer> inspectable=new ArrayList<>(routeLayers);
            if (resources!=null) inspectable.addAll(resources.layers());
            for (int i=inspectable.size()-1;i>=0;i--) {
                VectorLayer layer=inspectable.get(i); List<SelectItem> hits=control.identifySelections(location,layer);
                if (hits==null || hits.isEmpty()) continue;
                Record record=((SFeatureCls)layer.getData()).getAtt(hits.get(0).getOid());
                if (record==null) throw new IllegalStateException("MapGIS 对象属性读取失败");
                try {
                    StringBuilder text=new StringBuilder("图层："+layer.getName()+"\nMapGIS OID："+hits.get(0).getOid()+"\n");
                    var fields=record.getFields();
                    try { for (short f=0;f<fields.getFieldCount();f++) { var field=fields.getField(f);
                            try { text.append(field.getFieldName()).append("：").append(record.getFieldVal(f)).append('\n'); }
                            finally { field.dispose(); } } }
                    finally { fields.dispose(); }
                    details.setText(text.toString());
                    if (reportDirectory!=null) Files.writeString(reportDirectory.resolve("selected-route-object-"+UUID.randomUUID()+".txt"),
                            text.toString(),StandardOpenOption.CREATE_NEW);
                    log.accept("MapGIS 路线/资源对象查询："+layer.getName()); capture.run();
                } finally { record.dispose(); }
                return;
            }
        } catch (Exception | LinkageError error) { fail("地图属性查询",error); }
    }
    private void fail(String action,Throwable error) {
        error.printStackTrace(System.err); status.setText(action+"未完成："+error.getMessage()); log.accept(status.getText());
    }
    @Override public void close() { stopSimulation(); }
    private static EmergencyRoutePlanner.Result combine(EmergencyRoutePlanner.Result first,EmergencyRoutePlanner.Result second) {
        Set<Integer> blocked=new HashSet<>(first.blockedEdges()); blocked.addAll(second.blockedEdges());
        return new EmergencyRoutePlanner.Result(join(first.original(),second.original()),
                join(first.optimized(),second.optimized()),Set.copyOf(blocked),
                first.dangerousEdgesAvoided()+second.dangerousEdgesAvoided(),first.detour()||second.detour());
    }
    private static EmergencyRoutePlanner.Route join(EmergencyRoutePlanner.Route a,EmergencyRoutePlanner.Route b) {
        List<Integer> nodes=new ArrayList<>(a.nodes()); nodes.addAll(b.nodes().subList(1,b.nodes().size()));
        List<Integer> edges=new ArrayList<>(a.edges()); edges.addAll(b.edges());
        String level=a.riskLevel().equals("HIGH")||b.riskLevel().equals("HIGH")?"HIGH":
                a.riskLevel().equals("MEDIUM")||b.riskLevel().equals("MEDIUM")?"MEDIUM":"LOW";
        return new EmergencyRoutePlanner.Route(List.copyOf(nodes),List.copyOf(edges),
                a.distanceMetres()+b.distanceMetres(),a.impedanceMetres()+b.impedanceMetres(),
                a.estimatedMinutes()+b.estimatedMinutes(),level);
    }
}
