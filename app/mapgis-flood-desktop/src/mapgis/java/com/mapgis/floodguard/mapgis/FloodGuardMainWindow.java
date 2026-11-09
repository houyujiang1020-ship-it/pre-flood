package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.DamagePrediction;
import com.mapgis.floodguard.business.DemoController;
import com.mapgis.floodguard.business.DemoDataset;
import com.mapgis.floodguard.business.JudgeDemoMode;
import com.mapgis.floodguard.business.ResultValidator;
import com.mapgis.floodguard.business.CompetitionScenario;
import com.mapgis.floodguard.business.ScenarioManager;
import com.mapgis.floodguard.report.ReportGenerator;
import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.geodatabase.SFeatureCls;
import com.zondy.mapgis.map.Map;
import com.zondy.mapgis.map.MapLayer;
import com.zondy.mapgis.map.VectorLayer;
import com.zondy.mapgis.map.LayerState;
import com.zondy.mapgis.pluginengine.IApplication;
import com.zondy.mapgis.pluginengine.plugin.IMapContentsView;
import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.scene.Node;
import javafx.scene.SnapshotParameters;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.scene.image.WritableImage;
import javafx.stage.DirectoryChooser;
import javafx.stage.FileChooser;
import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.File;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;

/** One desktop workspace around the installed MapGIS MapControl and native analysis panels. */
public final class FloodGuardMainWindow extends BorderPane implements AutoCloseable {
    private final IApplication host;
    private final IApplication mapApplication;
    private final MapControl mapControl = new MapControl();
    private final Map map = new Map();
    private final TextArea log = new TextArea();
    private final Label buildings = new Label("—"), floodedBuildings = new Label("—");
    private final Label roadLength = new Label("—"), population = new Label("—"), risk = new Label("未评估");
    private final Label currentArea = new Label("—"), riskScore = new Label("—"), blockedRoad = new Label("—");
    private final Label rescueDistance = new Label("—"), rescueTime = new Label("—"), rescueRoads = new Label("—"), rescueAvoided = new Label("—");
    private final Label source = new Label("请选择数据并运行 MapGIS 分析");
    private final VBox workArea = new VBox(8);
    private final TreeView<String> menu = new TreeView<>();
    private final ObjectMapper json = new ObjectMapper();
    private FloodMainPanel inference;
    private ExposurePanel exposure;
    private DispatchPanel dispatch;
    private EmergencyDispatchPanel emergencyDispatch;
    private DamageThematicPanel thematic;
    private RiskAssessmentPanel riskAssessment;
    private Path thematicManifest;
    private Path riskReport;
    private Path mask, patches;
    private final DashboardPanel dashboard = new DashboardPanel();
    private final Label scenarioStatus=new Label("案例：未加载"), modelStatus=new Label("模型：未运行"),
            gisStatus=new Label("GIS：待分析"), progressStatus=new Label("进度：0/8");
    private ScenarioManager scenarioManager;
    private ScenarioPanel scenarioPanel;
    private ScenarioManager.Scenario currentScenario;
    private boolean verifiedCompetitionScenario;
    private ScreenshotManager screenshots;
    private boolean competitionMode;
    private boolean demoRunning;
    private DemoController.Result latestDemo;
    private Path finalReport, aiEvidence, damageEvidence, resourceEvidence;
    private MapGisDamageThematicImporter.Result nativeDamage;
    private double floodAreaSquareMetres;
    private Path evidenceRoot = Path.of(System.getProperty("floodguard.evidence",
            Path.of(System.getProperty("floodguard.output", "runtime/desktop-evidence")).resolve("desktop-evidence").toString()));

    public FloodGuardMainWindow(IApplication host) {
        this.host = Objects.requireNonNull(host);
        mapControl.setMap(map);
        mapApplication = bindMap(host, mapControl);
        setPadding(new Insets(8));
        setStyle("-fx-background-color:#e9eef3;");
        setTop(toolbar());
        setLeft(navigation());
        setCenter(center());
        setRight(metrics());
        setBottom(new VBox(logPane(),statusBar()));
        try { scenarioManager=new ScenarioManager(Path.of(System.getProperty("floodguard.scenarios","outputs/scenarios"))); }
        catch (Exception error) { fail("案例管理初始化",error); }
        open(Boolean.getBoolean("floodguard.auto.acceptance") ? "洪水检测" : "数据管理");
        appendLog("工作台已创建；中央视图使用 MapGIS 官方 MapControl。");
    }

    private static IApplication bindMap(IApplication host, MapControl control) {
        IMapContentsView view = (IMapContentsView) Proxy.newProxyInstance(
                IMapContentsView.class.getClassLoader(), new Class<?>[]{IMapContentsView.class},
                (proxy, method, args) -> {
                    if (method.getName().equals("getMapControl")) return control;
                    if (method.getName().equals("toString")) return "FloodGuard MapGIS map view";
                    throw new UnsupportedOperationException("Unsupported map view operation: " + method.getName());
                });
        return (IApplication) Proxy.newProxyInstance(IApplication.class.getClassLoader(),
                new Class<?>[]{IApplication.class}, (proxy, method, args) -> {
                    if (method.getName().equals("getActiveContentsView")) return view;
                    try { return method.invoke(host, args); }
                    catch (InvocationTargetException error) { throw error.getCause(); }
                });
    }

    private Node toolbar() {
        Label title = new Label("MapGIS-FloodGuard  洪涝灾害智能分析与应急决策");
        title.setStyle("-fx-font-size:19px;-fx-font-weight:bold;-fx-text-fill:#143b5d;");
        Button full = button("全图", () -> { mapControl.restoreWnd(); mapControl.refreshWnd(); appendLog("地图：已恢复全图范围"); });
        Button plus = button("放大", () -> { mapControl.zoomIn(); appendLog("地图：放大"); });
        Button minus = button("缩小", () -> { mapControl.zoomOut(); appendLog("地图：缩小"); });
        Button capture = button("保存验收截图", this::capture);
        Button loadCase=button("加载案例",()->open("数据管理"));
        Button loadRealCase=button("加载真实案例",this::loadCompetitionScenario);
        Button start=button("开始分析",this::startRegularDemo);
        Button competition=button("比赛演示",this::startCompetitionDemo);
        Button riskButton=button("风险评估",()->open("风险评估"));
        Button routeButton=button("路径规划",()->open("应急调度"));
        Button reportButton=button("生成报告",this::generateFinalReport);
        FlowPane actions=new FlowPane(8,5,loadCase,loadRealCase,start,competition,riskButton,routeButton,
                reportButton,full,plus,minus,capture);
        VBox bar=new VBox(6,title,actions);
        bar.setPadding(new Insets(8)); bar.setStyle("-fx-background-color:white;");
        return bar;
    }

    private Node navigation() {
        TreeItem<String> root = new TreeItem<>("功能菜单"); root.setExpanded(true);
        root.getChildren().addAll(List.of("数据管理","开始灾害演练","洪水检测","灾损分析","风险评估","应急路径","资源调度","应急调度","系统报告")
                .stream().map(TreeItem::new).toList());
        menu.setRoot(root); menu.setShowRoot(false); menu.setPrefWidth(170);
        menu.getSelectionModel().selectedItemProperty().addListener((o,a,b) -> {
            if (b != null) open(b.getValue());
        });
        return menu;
    }

    private Node center() {
        StackPane mapHolder = new StackPane(mapControl);
        mapHolder.setMinHeight(320);
        mapHolder.setStyle("-fx-background-color:#d8e5ed;-fx-border-color:#a9bbc9;");
        mapControl.prefWidthProperty().bind(mapHolder.widthProperty());
        mapControl.prefHeightProperty().bind(mapHolder.heightProperty());
        VBox.setVgrow(mapHolder, Priority.ALWAYS);
        workArea.setPadding(new Insets(8)); workArea.setPrefHeight(250);
        ScrollPane tools = new ScrollPane(workArea); tools.setFitToWidth(true); tools.setPrefHeight(270);
        SplitPane split = new SplitPane(mapHolder, tools);
        split.setOrientation(javafx.geometry.Orientation.VERTICAL);
        split.setDividerPositions(0.64);
        return split;
    }

    private Node metrics() {
        VBox pane = new VBox(13, heading("分析结果"), metric("建筑数量",buildings), metric("受淹建筑数量",floodedBuildings),
                metric("道路长度",roadLength), metric("受影响人口",population), metric("当前区域",currentArea),
                metric("风险等级",risk), metric("综合风险指数",riskScore), metric("道路阻断",blockedRoad),new Separator(), source);
        pane.getChildren().addAll(new Separator(),dashboard,new Separator(),heading("应急路径"),metric("路线长度",rescueDistance),
                metric("预计时间",rescueTime),metric("经过道路",rescueRoads),metric("避开危险道路",rescueAvoided));
        pane.setPadding(new Insets(14)); pane.setPrefWidth(220); pane.setStyle("-fx-background-color:white;");
        source.setWrapText(true);
        ScrollPane scroll=new ScrollPane(pane); scroll.setFitToWidth(true); scroll.setPrefWidth(230);
        return scroll;
    }
    private Node metric(String title, Label value) {
        Label caption = new Label(title); caption.setStyle("-fx-text-fill:#617686;");
        value.setStyle("-fx-font-size:17px;-fx-font-weight:bold;");
        return new VBox(3, caption, value);
    }
    private Label heading(String text) { Label label = new Label(text); label.setStyle("-fx-font-size:17px;-fx-font-weight:bold;"); return label; }

    private Node logPane() {
        log.setEditable(false); log.setWrapText(true); log.setPrefRowCount(5);
        VBox box = new VBox(5, new Label("运行日志 · 模型调用 / GIS 分析 / 路径 / 异常"), log);
        box.setPadding(new Insets(8)); box.setStyle("-fx-background-color:white;");
        return box;
    }
    private Node statusBar() {
        HBox bar=new HBox(18,scenarioStatus,modelStatus,gisStatus,progressStatus);
        bar.setPadding(new Insets(5,10,5,10)); bar.setStyle("-fx-background-color:#dce8f0;"); return bar;
    }
    private Button button(String title, Runnable action) {
        Button button = new Button(title);
        button.setOnAction(e -> { try { action.run(); } catch (Exception | LinkageError error) { fail(title,error); } });
        return button;
    }
    private void appendLog(String message) {
        String line = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")) + "  " + message;
        if (Platform.isFxApplicationThread()) log.appendText(line + System.lineSeparator());
        else Platform.runLater(() -> log.appendText(line + System.lineSeparator()));
    }
    private void fail(String operation, Throwable error) {
        error.printStackTrace(System.err);
        appendLog(operation + "失败：" + error.getMessage());
    }
    private void show(Node... nodes) { workArea.getChildren().setAll(nodes); }

    private void open(String item) {
        try {
            switch (item) {
                case "数据管理" -> dataPage();
                case "开始灾害演练" -> demoPage();
                case "洪水检测" -> inferencePage();
                case "灾损分析" -> exposurePage();
                case "风险评估" -> riskPage();
                case "应急路径", "资源调度", "应急调度" -> dispatchPage();
                case "系统报告" -> reportPage();
                default -> throw new IllegalArgumentException("未知菜单：" + item);
            }
            appendLog("打开功能：" + item);
        } catch (Exception | LinkageError error) { fail(item,error); }
    }
    private void dataPage() {
        if (scenarioManager!=null && scenarioPanel==null) scenarioPanel=new ScenarioPanel(scenarioManager,this::selectScenario,this::appendLog);
        show(heading("数据管理"), new Label("导入 GeoTIFF 等已配准影像；人口与实体数据须保留来源和空间参考。"),
                scenarioPanel==null?new Label("案例目录不可用"):scenarioPanel,
                button("检查内置演示素材",this::auditDemoDataset),
                button("导入模拟 REPLAY 原生图层",this::importReplayNativeLayers),
                button("构建模拟 REPLAY 路网（诊断）",this::buildReplayNetwork),
                new HBox(8, button("加载底图", () -> loadRaster("底图")),
                        button("加载遥感影像", () -> loadRaster("遥感影像")),
                        button("加载洪水结果", () -> loadRaster("洪水结果")),
                        button("加载建筑灾损图层", () -> loadVector("建筑灾损")),
                        button("加载道路灾损图层", () -> loadVector("道路灾损")),
                        button("加载人口分布图层", () -> loadVector("人口分布")),
                        button("加载原生路网", this::loadNetwork)),
                button("刷新图层清单", this::listLayers));
        listLayers();
    }
    private void selectScenario(ScenarioManager.Scenario scenario) {
        currentScenario=scenario; verifiedCompetitionScenario=false; scenarioStatus.setText("案例："+scenario.name());
        mask=null; patches=null; exposure=null; dispatch=null;
        if (inference!=null) inference.setInputPaths(scenario.preImage(),scenario.postImage());
        appendLog("已加载案例："+scenario.name()+"；AI 模式="+scenario.aiMode()+"；模拟="+scenario.simulated());
        appendLog("案例影像：pre="+scenario.preImage()+"；post="+scenario.postImage()
                +"；旧 AI 空间结果与实体核查缓存已清除；REPLAY 不会作为 LIVE_AI 掩膜复用");
    }
    private void loadCompetitionScenario() {
        FileChooser chooser=new FileChooser(); chooser.setTitle("选择已核验真实案例清单");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("JSON","*.json"));
        File selected=chooser.showOpenDialog(getScene().getWindow()); if (selected==null) return;
        try { selectScenario(new com.mapgis.floodguard.business.OfficialDemoScenario().load(selected.toPath()));
            verifiedCompetitionScenario=true;
            if (scenarioPanel!=null) scenarioPanel.fill(currentScenario);
            appendLog("真实案例来源与 SHA-256 已预检；MapGIS 图层连接与空间结果仍需运行核验："+selected); }
        catch (Exception error) { fail("加载真实案例",error); }
    }
    private void auditDemoDataset() {
        try {
            Path report=new DemoDataset().auditProject();
            appendLog("内置演示素材核查："+report+"；原始素材尚不能单独完成原生 GIS 闭环");
        } catch (Exception error) { fail("检查内置演示素材",error); }
    }
    private void importReplayNativeLayers() {
        Path output=null;
        try {
            Path source=DemoDataset.repositoryRoot().resolve("data/demo/replay-p007");
            output=source.resolve("native-import-"+UUID.randomUUID());
            Path evidence=MapGisReplayNativeImporter.importCase(source,output);
            JsonNode layers=json.readTree(evidence.toFile()).path("layers");
            for (String name:List.of("replay_buildings","replay_roads","replay_population",
                    "replay_administrative","replay_flood_extent")) {
                String url=layers.path(name).path("url").asText();
                if (url.isBlank()) throw new IllegalStateException("原生导入缺少图层 URL："+name);
                attachVector(url,"模拟 REPLAY · "+name);
            }
            appendLog("模拟 REPLAY 原生图层已导入并加载；验证记录："+evidence.toAbsolutePath());
        } catch (Exception | LinkageError error) {
            fail("导入模拟 REPLAY 原生图层",error);
            if (output!=null) appendLog("原生导入诊断记录："+output.resolve("native-import.json").toAbsolutePath());
        }
    }
    private void buildReplayNetwork() {
        Path output=null;
        try {
            Path source=DemoDataset.repositoryRoot().resolve("data/demo/replay-p007/network-source");
            output=source.getParent().resolve("network-"+UUID.randomUUID());
            Path evidence=MapGisExerciseNetworkBuilder.build(source,output);
            JsonNode result=json.readTree(evidence.toFile());
            if (result.path("native_network_created").asBoolean()) {
                attachVector(result.path("roads_url").asText(),"模拟 REPLAY · 路网源道路");
                attachNetwork(result.path("network_url").asText());
                try {
                    com.zondy.mapgis.geodatabase.net.NetCls nativeNetwork=null;
                    for (int i=0;i<map.getLayerCount();i++)
                        if (result.path("network_url").asText().equals(String.valueOf(map.getLayer(i).getURL()))
                                && map.getLayer(i).getData() instanceof com.zondy.mapgis.geodatabase.net.NetCls candidate)
                            nativeNetwork=candidate;
                    if (nativeNetwork==null) throw new IllegalStateException("原生路网图层未连接");
                    Path draft=source.getParent().resolve("road-status-draft.json");
                    Path ledger=MapGisReplayRoadLedger.create(draft,evidence,nativeNetwork);
                    dispatchPage();
                    Path mapping=emergencyDispatch.loadScenarioRoadStatuses(ledger);
                    appendLog("模拟封路源 OID→原生边映射已核查："+mapping.toAbsolutePath());
                } catch (Exception | LinkageError mappingError) { fail("模拟封路映射核查",mappingError); }
            }
            appendLog("模拟 REPLAY 路网诊断：拓扑="+result.path("native_network_created").asBoolean()
                    +"；路线验收="+result.path("exercise_routes_verified").asBoolean()
                    +"；dispatch_ready="+result.path("dispatch_ready").asBoolean()
                    +"；证据="+evidence.toAbsolutePath());
        } catch (Exception | LinkageError error) {
            fail("构建模拟 REPLAY 路网",error);
            if (output!=null) appendLog("路网诊断记录："+output.resolve("network-build.json").toAbsolutePath());
        }
    }
    private void demoPage() {
        show(heading("一键灾害演练"),new Label("依次加载数据、读取模型结果、生成 MapGIS 灾损和风险图层、封路绕行、匹配资源并导出综合报告。"),
                new Label(currentScenario==null?"请先在数据管理中创建或加载案例。":"当前案例："+currentScenario.name()),
                button("开始灾害演练",this::startRegularDemo));
    }
    private void loadRaster(String role) {
        FileChooser chooser = new FileChooser(); chooser.setTitle("选择" + role + "栅格");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("地理参考栅格", "*.tif", "*.tiff"));
        File file = chooser.showOpenDialog(getScene().getWindow()); if (file == null) return;
        new MapGisResultLayerLoader().load(mapApplication, file.toPath(), role + " · " + file.getName());
        appendLog("MapGIS 已加载" + role + "：" + file);
        listLayers();
    }
    private void loadVector(String role) {
        TextInputDialog dialog = new TextInputDialog();
        dialog.setTitle("MapGIS 图层数据源");
        dialog.setHeaderText("输入 MapGIS SDK 可连接的" + role + "图层 URL");
        dialog.setContentText("数据源 URL：");
        Optional<String> selected = dialog.showAndWait();
        if (selected.isEmpty()) return;
        String url = selected.get().trim();
        if (url.isBlank()) throw new IllegalArgumentException("图层 URL 不能为空");
        VectorLayer layer = new VectorLayer();
        layer.setURL(url);
        if (!layer.connectData()) { layer.dispose(); throw new IllegalArgumentException("MapGIS 无法连接矢量数据：" + url); }
        layer.setName(role); layer.setState(LayerState.Visible);
        map.append(layer); mapControl.restoreWnd(); mapControl.refreshWnd();
        appendLog("MapGIS 已加载" + role + "：" + layer.getURL()); listLayers();
    }
    private void loadNetwork() {
        TextInputDialog dialog=new TextInputDialog(); dialog.setTitle("MapGIS 原生路网");
        dialog.setHeaderText("输入 MapGIS NetCls 图层 URL"); dialog.setContentText("路网 URL：");
        Optional<String> selected=dialog.showAndWait(); if (selected.isEmpty()) return;
        String url=selected.get().trim(); if (url.isBlank()) throw new IllegalArgumentException("路网 URL 不能为空");
        com.zondy.mapgis.map.NetClsLayer layer=new com.zondy.mapgis.map.NetClsLayer(); layer.setURL(url);
        if (!layer.connectData() || !(layer.getData() instanceof com.zondy.mapgis.geodatabase.net.NetCls)) {
            layer.dispose(); throw new IllegalArgumentException("MapGIS 原生路网连接失败："+url);
        }
        layer.setName("MapGIS 原生路网"); layer.setState(LayerState.Visible);
        map.append(layer); mapControl.restoreWnd(); mapControl.refreshWnd();
        appendLog("MapGIS 已加载原生路网："+url); listLayers();
    }
    private void listLayers() {
        StringBuilder listing = new StringBuilder("当前 MapGIS 图层：");
        for (int i=0;i<map.getLayerCount();i++) listing.append("\n• ").append(map.getLayer(i).getName());
        if (map.getLayerCount()==0) listing.append("暂无");
        if (workArea.getChildren().size() > 0 && "数据管理".equals(menu.getSelectionModel().getSelectedItem()==null ? "数据管理" : menu.getSelectionModel().getSelectedItem().getValue())) {
            workArea.getChildren().removeIf(n -> "layer-list".equals(n.getId()));
            Label label = new Label(listing.toString()); label.setId("layer-list"); workArea.getChildren().add(label);
        }
        long count = 0; boolean hasBuildings = false;
        for (int i=0;i<map.getLayerCount();i++) {
            MapLayer layer = map.getLayer(i);
            if (layer instanceof VectorLayer vector && vector.getData() instanceof SFeatureCls features
                    && features.getGeomType() == com.zondy.mapgis.geometry.GeomType.GeomReg
                    && layer.getName().contains("建筑")) { count += features.getObjCount(); hasBuildings = true; }
        }
        if (hasBuildings) { buildings.setText(Long.toString(count)); source.setText("建筑数来自当前 MapGIS 实体图层；受淹数等待相交核查。"); }
        updateRoadLength();
    }
    private void updateRoadLength() {
        double metres = 0; boolean found = false;
        for (int i=0;i<map.getLayerCount();i++) {
            MapLayer layer = map.getLayer(i);
            if (!(layer instanceof VectorLayer vector) || !(vector.getData() instanceof SFeatureCls features)
                    || features.getGeomType() != com.zondy.mapgis.geometry.GeomType.GeomLin
                    || !layer.getName().contains("道路")) continue;
            String wkt = layer.getSrefInfo() == null ? "" : layer.getSrefInfo().toWkt();
            if (!wkt.startsWith("PROJCS[") || !wkt.toLowerCase(Locale.ROOT).contains("metre")) {
                roadLength.setText("待投影核验"); appendLog("道路长度：图层需米制投影，未将经纬度当米计算"); return;
            }
            found = true;
            com.zondy.mapgis.geodatabase.QueryDef query = new com.zondy.mapgis.geodatabase.QueryDef();
            com.zondy.mapgis.geodatabase.RecordSet records = null;
            try {
                records = features.query(query);
                if (records == null) throw new IllegalStateException("MapGIS 道路查询失败");
                int count = records.getCount(); if (count < 0) throw new IllegalStateException("无效道路记录数");
                if (count > 0) records.moveFirst();
                for (int n=0;n<count;n++) {
                    com.zondy.mapgis.geometry.Geometry geometry = records.getGeometry();
                    if (geometry == null) throw new IllegalStateException("道路几何缺失");
                    try {
                        if (geometry instanceof com.zondy.mapgis.geometry.GeoLine line) metres += line.calLength();
                        else if (geometry instanceof com.zondy.mapgis.geometry.GeoMultiLine lines) metres += lines.calLength();
                        else throw new IllegalStateException("非线状道路几何");
                    } finally { geometry.dispose(); }
                    if (n+1<count) records.moveNext();
                }
            } finally { if (records != null) records.dispose(); query.dispose(); }
        }
        if (found) { roadLength.setText(String.format(Locale.ROOT,"%.2f m",metres)); appendLog("MapGIS 原生道路几何总长："+metres+" m"); }
    }
    private void inferencePage() {
        if (inference == null) {
            inference = new FloodMainPanel(mapApplication);
            inference.setLogSink(this::appendLog);
            inference.setSpatialSink((m,p) -> {
                mask=m; patches=p; exposure=null; dispatch=null;
                appendLog(m==null?"影像输入已切换；旧空间结果及实体核查已失效":"空间结果："+m);
            });
            if (currentScenario!=null) inference.setInputPaths(currentScenario.preImage(),currentScenario.postImage());
        }
        show(inference);
    }
    private void exposurePage() {
        if (thematic == null) {
            thematic = new DamageThematicPanel(mapControl,evidenceRoot,this::appendLog,result -> {
                thematicManifest = result.manifest();
                listLayers();
                int normal = result.counts().getOrDefault("BUILDING_NORMAL",0);
                int flooded = result.counts().getOrDefault("BUILDING_FLOODED",0);
                buildings.setText(Integer.toString(normal+flooded));
                floodedBuildings.setText(flooded + " 预测");
                source.setText("AI 对象预测 · MapGIS 专题图层；对象状态待现场核验。");
                captureLater();
            },this::captureLater);
        }
        Button legacy = button("AI 斑块与实体相交核查",this::legacyExposurePage);
        legacy.setDisable(mask == null || !Files.isRegularFile(mask));
        show(thematic, legacy);
        Path automatic = Path.of(System.getProperty("floodguard.prediction",
                Path.of(System.getProperty("floodguard.output", "outputs"),"flood_prediction.json").toString()));
        thematic.autoLoad(automatic);
    }
    private void legacyExposurePage() {
        if (mask == null || !Files.isRegularFile(mask)) {
            show(heading("灾损分析"), new Label("请先在“洪水检测”中完成空间化与 MapGIS 图层加载。"),
                    button("前往洪水检测", () -> open("洪水检测")));
            return;
        }
        if (patches == null || !Files.isRegularFile(patches)) {
            patches = mask.resolveSibling("predicted-patches-" + UUID.randomUUID() + ".geojson");
            try { new MapGisMaskVectorizer().export(mask, patches); }
            catch (java.io.IOException error) { throw new IllegalStateException("MapGIS 斑块导出失败", error); }
        }
        if (exposure == null) {
            exposure = new ExposurePanel(mapApplication,mask,patches,() -> this.mask);
            exposure.setLogSink(this::appendLog);
            exposure.setAssessmentSink((total,result) -> {
                if (result == null) { floodedBuildings.setText("—"); return; }
                buildings.setText(Long.toString(total));
                floodedBuildings.setText(result.candidateBuildings() + " 候选");
                source.setText("MapGIS 原生相交查询；候选暴露不等于确认损毁。");
            });
            exposure.setDispatchSink(panel -> { dispatch=panel; dispatch.setLogSink(this::appendLog); open("资源调度"); });
        }
        show(exposure);
    }
    private void dispatchPage() {
        if (emergencyDispatch==null) emergencyDispatch=new EmergencyDispatchPanel(mapControl,evidenceRoot,this::appendLog,result->{
            rescueDistance.setText(String.format(Locale.ROOT,"%.2f km",result.optimized().distanceMetres()/1000));
            rescueTime.setText(String.format(Locale.ROOT,"%.1f min",result.optimized().estimatedMinutes()));
            rescueRoads.setText(Integer.toString(result.optimized().edges().size()));
            rescueAvoided.setText(Integer.toString(result.dangerousEdgesAvoided()));
        },this::captureLater);
        emergencyDispatch.refresh();
        if (dispatch!=null) show(emergencyDispatch,button("查看旧版核查调度面板",()->show(dispatch)));
        else show(emergencyDispatch);
    }
    private void riskPage() {
        if (riskAssessment==null) riskAssessment=new RiskAssessmentPanel(mapControl,evidenceRoot,this::appendLog,result->{
            riskReport=result.reportJson();
            if (!result.areas().isEmpty()) {
                var first=result.areas().get(0);
                showRiskArea(first);
            }
            captureLater();
        },this::showRiskArea,this::captureLater);
        show(riskAssessment,button("查看旧版手工指标计算",this::legacyRiskPage));
        riskAssessment.autoRunWhenReady();
    }
    private void showRiskArea(FloodRiskAssessment.AreaResult area) {
        currentArea.setText(area.area());
        risk.setText(area.riskLevel()==null?"待补数据":area.riskLevel());
        riskScore.setText(area.riskScore()==null?"—":String.format(Locale.ROOT,"%.3f",area.riskScore()));
        population.setText(area.affectedPopulation()==null?"未计算":String.format(Locale.ROOT,"%.0f",area.affectedPopulation()));
        buildings.setText(Integer.toString(area.totalBuildings()));
        floodedBuildings.setText(Integer.toString(area.damagedBuildings()));
        roadLength.setText(String.format(Locale.ROOT,"%.2f km",area.totalRoadMetres()/1000));
        blockedRoad.setText(String.format(Locale.ROOT,"%.2f km",area.blockedRoadMetres()/1000));
        source.setText(area.reason().isBlank()?"MapGIS 原生空间叠加："+riskReport:"部分结果："+area.reason());
    }
    private void legacyRiskPage() {
        show(heading("旧版手工指标计算"),button("计算风险",this::calculateRisk),button("读取人口估算证据",this::readPopulation),
                button("返回 MapGIS 风险评估",this::riskPage));
    }
    private void calculateRisk() {
        FileChooser chooser = new FileChooser(); chooser.setTitle("选择五项风险指标（0—1）");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("JSON","*.json"));
        File file = chooser.showOpenDialog(getScene().getWindow()); if (file == null) return;
        try {
            JsonNode data = json.readTree(file);
            if (!"GIS_VERIFIED".equals(data.path("status").asText())
                    || !"MapGIS".equals(data.path("engine").asText()))
                throw new IllegalArgumentException("风险输入需要 MapGIS 已核验状态，缺失指标不得按零处理");
            java.util.Map<String,Double> indicators = new LinkedHashMap<>();
            for (String key : List.of("flood","population","buildingDamage","roadAccessibility","medicalAccessibility")) {
                if (!data.path("indicators").path(key).isNumber()) throw new IllegalArgumentException("缺少指标："+key);
                indicators.put(key,data.path("indicators").path(key).asDouble());
            }
            var calculator = new com.mapgis.floodguard.business.RiskCalculator(com.mapgis.floodguard.business.RiskCalculator.Weights.defaults());
            double score = calculator.score(indicators);
            risk.setText(calculator.level(score) + " / " + String.format(Locale.ROOT,"%.3f",score));
            source.setText("风险输入：" + file + "；请核验其 MapGIS 计算来源。");
            appendLog("风险计算完成；输入=" + file + "，分值=" + score);
        } catch (Exception error) { fail("风险计算",error); }
    }
    private void readPopulation() {
        FileChooser chooser = new FileChooser(); chooser.setTitle("选择已有 MapGIS 人口分析证据");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("JSON","*.json"));
        File file = chooser.showOpenDialog(getScene().getWindow()); if (file == null) return;
        try {
            JsonNode data = json.readTree(file);
            JsonNode value = data.path("estimated_affected_population");
            if (!value.isNumber()) throw new IllegalArgumentException("文件缺少受影响人口估算字段");
            if (!"REFERENCE_PREPARATION".equals(data.path("status").asText()))
                throw new IllegalArgumentException("不是已知人口估算证据状态");
            population.setText(value.asText() + " 参考估算"); source.setText("人口参考估算，MapGIS 原生复算待完成：" + file);
            appendLog("已读取人口估算：" + file);
        } catch (Exception error) { fail("人口证据",error); }
    }
    private void reportPage() {
        Path routeReport=emergencyDispatch==null?null:emergencyDispatch.latestRouteReport();
        show(heading("系统报告"),new Label("风险报告："+(riskReport==null?"未生成":riskReport)),
                new Label("应急路径报告："+(routeReport==null?"未生成":routeReport)),
                new Label("综合报告："+(finalReport==null?"未生成":finalReport)),
                button("生成综合报告",this::generateFinalReport),
                button("保存当前截图与日志",this::capture));
    }
    private void startDemo() {
        if (demoRunning) throw new IllegalStateException("已有演练正在运行");
        if (currentScenario==null) throw new IllegalStateException("请先加载案例");
        try {
            demoRunning=true;
            final boolean submission=competitionMode;
            final JudgeDemoMode judge=submission?new JudgeDemoMode():null;
            final Path timeline=Path.of("submission/judge_demo_timeline.json");
            screenshots=new ScreenshotManager(Path.of(submission?"Final_Evidence":"outputs/screenshots"),
                    "demo-"+UUID.randomUUID(),submission);
            screenshots.capture(ScreenshotManager.Scene.HOME,this,map.getLayerCount());
            DemoController controller=new DemoController();
            CompletionStage<DemoController.Result> run=controller.start(currentScenario,Path.of("outputs/demo-runs"),
                    this::executeDemoStep,new DemoController.Listener() {
                        @Override public void started(DemoController.Step step,int done,int total) {
                            progressStatus.setText("进度："+done+"/"+total+" · "+step); appendLog("演练开始："+step);
                        }
                        @Override public void completed(DemoController.Step step,Path evidence,int done,int total) {
                            progressStatus.setText("进度："+done+"/"+total); appendLog("演练完成："+step+"；证据="+evidence);
                            if (judge!=null) { judge.completed(step,evidence);
                                try { judge.save(timeline); } catch (Exception error) { fail("评委演示时间记录",error); } }
                        }
                        @Override public void failed(DemoController.Step step,Throwable error) {
                            progressStatus.setText("演练失败："+step); fail("演练步骤 "+step,error);
                            if (judge!=null) { judge.finish(false,error.toString());
                                try { judge.save(timeline); } catch (Exception saveError) { fail("评委演示时间记录",saveError); } }
                        }
                    });
            run.whenComplete((result,error)->{ demoRunning=false; if (error==null) {
                latestDemo=result; gisStatus.setText("GIS：演练完成"); appendLog("完整演练证据："+result.ledger());
                if (judge!=null) { judge.finish(true,null);
                    try { judge.save(timeline); } catch (Exception saveError) { fail("评委演示时间记录",saveError); } }
                if (submission) appendLog("比赛八张阶段截图已核查："+screenshots.directory());
            }});
        } catch (Exception error) { demoRunning=false; fail("开始灾害演练",error); }
    }
    private void startRegularDemo() {
        if (demoRunning) throw new IllegalStateException("已有演练正在运行");
        competitionMode=false; startDemo();
    }
    private void startCompetitionDemo() {
        if (demoRunning) throw new IllegalStateException("已有演练正在运行");
        competitionMode=true;
        if (!verifiedCompetitionScenario) {
            try { selectScenario(new com.mapgis.floodguard.business.CompetitionDemoMode().loadReadyScenario(
                    Path.of("DemoDataset_Final/06_scenario.json"))); }
            catch (Exception error) { fail("比赛演示案例预检",error); open("数据管理"); return; }
        }
        startDemo();
    }
    private CompletionStage<Path> executeDemoStep(DemoController.Step step,ScenarioManager.Scenario scenario,
                                                    java.util.Map<DemoController.Step,Path> evidence) throws Exception {
        Path result=switch(step) {
            case LOAD_DATA -> loadDemoData(scenario);
            case AI_DETECTION -> runDemoAi(scenario);
            case DAMAGE_THEMATIC -> runDemoDamage(scenario);
            case RISK_ASSESSMENT -> runDemoRisk(scenario);
            case ROAD_CLOSURE -> runDemoClosure(scenario);
            case ROUTE_PLANNING -> runDemoRoute(scenario);
            case RESOURCE_MATCHING -> runDemoResources();
            case FINAL_REPORT -> generateFinalReportPath(scenario);
        };
        ScreenshotManager.Scene scene=switch(step) {
            case LOAD_DATA -> ScreenshotManager.Scene.DATA; case AI_DETECTION -> ScreenshotManager.Scene.FLOOD;
            case DAMAGE_THEMATIC -> ScreenshotManager.Scene.DAMAGE;
            case RISK_ASSESSMENT -> ScreenshotManager.Scene.RISK; case ROAD_CLOSURE -> ScreenshotManager.Scene.CLOSURE;
            case ROUTE_PLANNING -> ScreenshotManager.Scene.ROUTE; case RESOURCE_MATCHING -> ScreenshotManager.Scene.RESOURCES;
            case FINAL_REPORT -> ScreenshotManager.Scene.REPORT;
        };
        if (scene==null) return CompletableFuture.completedFuture(result);
        CompletableFuture<Path> finished=new CompletableFuture<>();
        javafx.animation.PauseTransition pause=new javafx.animation.PauseTransition(javafx.util.Duration.millis(350));
        pause.setOnFinished(event->{ try { screenshots.capture(scene,this,map.getLayerCount());
                if (competitionMode && scene==ScreenshotManager.Scene.REPORT) screenshots.verifySubmissionComplete();
                finished.complete(result); }
            catch (Exception error) { finished.completeExceptionally(error); } });
        pause.play(); return finished;
    }
    private Path loadDemoData(ScenarioManager.Scenario scenario) throws Exception {
        for (String path:List.of(scenario.preImage(),scenario.postImage(),scenario.predictionJson(),
                scenario.resourceManifest(),scenario.roadStatusLedger()))
            if (!Files.isRegularFile(Path.of(path))) throw new IllegalArgumentException("案例源文件缺失："+path);
        new MapGisResultLayerLoader().load(mapApplication,Path.of(scenario.preImage()),"演练灾前影像");
        new MapGisResultLayerLoader().load(mapApplication,Path.of(scenario.postImage()),"演练灾后影像");
        attachVector(scenario.administrativeUrl(),"行政区域");
        attachVector(scenario.populationUrl(),"人口格网");
        attachVector(scenario.floodExtentUrl(),"真实洪水面");
        attachVector(scenario.sourceRoadsUrl(),"原始道路");
        attachNetwork(scenario.networkUrl());
        dispatchPage();
        emergencyDispatch.loadScenarioResources(Path.of(scenario.resourceManifest()));
        dashboard.resources(emergencyDispatch.availableResourceCount());
        gisStatus.setText("GIS：MapGIS 数据已加载");
        Path file=Files.createDirectories(evidenceRoot).resolve("demo-inputs-"+UUID.randomUUID()+".json");
        Files.writeString(file,json.writerWithDefaultPrettyPrinter().writeValueAsString(java.util.Map.of(
                "scenario",scenario.name(),"engine","MapGIS","layer_count",map.getLayerCount(),
                "resource_manifest",scenario.resourceManifest())));
        return file;
    }
    private void attachVector(String url,String label) {
        for (int i=0;i<map.getLayerCount();i++) if (url.equals(String.valueOf(map.getLayer(i).getURL()))) return;
        VectorLayer layer=new VectorLayer(); layer.setURL(url);
        if (!layer.connectData()) { layer.dispose(); throw new IllegalStateException("MapGIS 图层连接失败："+label+" · "+url); }
        layer.setName(label); layer.setState(LayerState.Visible); map.append(layer); mapControl.refreshWnd();
    }
    private void attachNetwork(String url) {
        for (int i=0;i<map.getLayerCount();i++) if (url.equals(String.valueOf(map.getLayer(i).getURL()))) return;
        com.zondy.mapgis.map.NetClsLayer layer=new com.zondy.mapgis.map.NetClsLayer(); layer.setURL(url);
        if (!layer.connectData() || !(layer.getData() instanceof com.zondy.mapgis.geodatabase.net.NetCls)) {
            layer.dispose(); throw new IllegalStateException("MapGIS 原生路网连接失败："+url);
        }
        layer.setName("演练原生路网"); layer.setState(LayerState.Visible); map.append(layer); mapControl.refreshWnd();
    }
    private Path runDemoAi(ScenarioManager.Scenario scenario) throws Exception {
        if ("LIVE_AI".equals(scenario.aiMode())) {
            try { new com.mapgis.floodguard.ai.AiServiceClient(java.net.URI.create(
                    System.getProperty("floodguard.ai.url","http://127.0.0.1:8765/"))).health(); }
            catch (Exception error) { modelStatus.setText("模型：服务异常");
                throw new IllegalStateException("AI推理服务不可用："+error.getMessage(),error); }
            modelStatus.setText("模型：实时链路未闭合");
            throw new IllegalStateException("实时 AI 服务目前仅生成掩膜，未生成与当前对象对应的 flood_prediction.json；请完成对象级桥接或选择标注为 REPLAY 的案例");
        }
        DamagePrediction.Dataset prediction=DamagePrediction.read(Path.of(scenario.predictionJson()));
        Path file=Files.createDirectories(evidenceRoot).resolve("ai-replay-"+UUID.randomUUID()+".json");
        Files.writeString(file,json.writerWithDefaultPrettyPrinter().writeValueAsString(java.util.Map.of(
                "mode","REPLAY","status","COMPLETE","source",scenario.predictionJson(),
                "object_count",prediction.features().size(),"simulated",scenario.simulated())));
        aiEvidence=file; modelStatus.setText("模型：预测结果回放"); open("洪水检测"); return file;
    }
    private Path runDemoDamage(ScenarioManager.Scenario scenario) throws Exception {
        var result=new MapGisDamageThematicImporter().importAndLoad(mapControl,Path.of(scenario.predictionJson()),evidenceRoot);
        nativeDamage=result;
        thematicManifest=result.manifest(); damageEvidence=result.manifest();
        int normal=result.counts().getOrDefault("BUILDING_NORMAL",0), flooded=result.counts().getOrDefault("BUILDING_FLOODED",0);
        buildings.setText(Integer.toString(normal+flooded)); floodedBuildings.setText(Integer.toString(flooded));
        gisStatus.setText("GIS：灾损专题完成"); show(heading("灾损专题地图"),new Label("MapGIS 原生对象专题图已生成："+result.manifest()));
        return result.manifest();
    }
    private Path runDemoRisk(ScenarioManager.Scenario scenario) throws Exception {
        if (riskAssessment==null) riskAssessment=new RiskAssessmentPanel(mapControl,evidenceRoot,this::appendLog,result->riskReport=result.reportJson(),
                this::showRiskArea,()->{});
        JsonNode urls=json.readTree(nativeDamage.manifest().toFile()).path("layer_urls");
        riskAssessment.bindScenarioSources(scenario.administrativeUrl(),scenario.populationUrl(),scenario.floodExtentUrl(),
                urls.path("BUILDING_NORMAL").asText(),urls.path("BUILDING_FLOODED").asText(),
                urls.path("ROAD_NORMAL").asText(),urls.path("ROAD_FLOODED").asText(),urls.path("ROAD_BLOCKED").asText(),
                scenario.sourceRoadsUrl());
        var result=riskAssessment.runScenario(scenario.areaNameField(),scenario.resourceRiskField(),
                Path.of(scenario.roadStatusLedger()),scenario.sourceRoadsUrl(),scenario.aiMode());
        riskReport=result.reportJson(); if (!result.areas().isEmpty()) { showRiskArea(result.areas().get(0)); dashboard.risk(result.areas().get(0)); }
        floodAreaSquareMetres=calculateFloodArea(scenario.floodExtentUrl()); dashboard.floodArea(floodAreaSquareMetres);
        gisStatus.setText("GIS：风险评估完成"); show(riskAssessment); return result.reportJson();
    }
    private double calculateFloodArea(String url) {
        for (int i=0;i<map.getLayerCount();i++) {
            MapLayer layer=map.getLayer(i); if (!url.equals(String.valueOf(layer.getURL())) || !(layer.getData() instanceof SFeatureCls cls)) continue;
            String wkt=layer.getSrefInfo()==null?"":layer.getSrefInfo().toWkt().toLowerCase(Locale.ROOT);
            if (!wkt.startsWith("projcs[") || !wkt.contains("metre")) throw new IllegalArgumentException("洪水面面积需要米制 MapGIS 图层");
            com.zondy.mapgis.geodatabase.QueryDef query=new com.zondy.mapgis.geodatabase.QueryDef();
            com.zondy.mapgis.geodatabase.RecordSet records=null;
            com.zondy.mapgis.geometry.Geometry union=null;
            try { records=cls.query(query); if (records==null) throw new IllegalStateException("MapGIS 洪水面查询失败");
                int count=records.getCount(); if (count>0) records.moveFirst();
                for (int n=0;n<count;n++) { var geometry=records.getGeometry();
                    if (!(geometry instanceof com.zondy.mapgis.geometry.GeoPolygon)) {
                        if (geometry!=null) geometry.dispose(); throw new IllegalArgumentException("洪水影响范围存在非面对象");
                    }
                    if (union==null) union=geometry;
                    else { var merged=com.zondy.mapgis.geometry.GeometryOperator.overlay(union,geometry,
                            com.zondy.mapgis.geometry.GeometryOperator.OverlayType.UNION,0.001);
                        union.dispose(); geometry.dispose();
                        if (merged==null) throw new IllegalStateException("MapGIS 洪水面合并失败"); union=merged; }
                    if (n+1<count) records.moveNext(); }
                return union==null?0:com.zondy.mapgis.geometry.GeometryOperator.calculateArea(union);
            } finally { if (union!=null) union.dispose(); if (records!=null) records.dispose(); query.dispose(); }
        }
        throw new IllegalArgumentException("洪水面图层未加载："+url);
    }
    private Path runDemoClosure(ScenarioManager.Scenario scenario) throws Exception {
        dispatchPage(); Path manifest=emergencyDispatch.loadScenarioRoadStatuses(Path.of(scenario.roadStatusLedger()));
        show(emergencyDispatch); return manifest;
    }
    private Path runDemoRoute(ScenarioManager.Scenario scenario) throws Exception {
        Path report;
        try { report=emergencyDispatch.planScenarioRoute(scenario.startResourceId(),scenario.targetResourceId(),scenario.speedKph()); }
        catch (IllegalStateException unreachable) { throw new IllegalStateException("当前区域不存在有效救援路径："+unreachable.getMessage(),unreachable); }
        show(emergencyDispatch); gisStatus.setText("GIS：救援路线完成"); return report;
    }
    private Path runDemoResources() throws Exception {
        resourceEvidence=emergencyDispatch.recommendScenarioResources();
        dashboard.resources(emergencyDispatch.availableResourceCount()); show(emergencyDispatch); return resourceEvidence;
    }
    private void generateFinalReport() {
        if (currentScenario==null) throw new IllegalStateException("请先加载案例");
        try { Path report=generateFinalReportPath(currentScenario); appendLog("综合报告已生成："+report); }
        catch (Exception error) { fail("生成综合报告",error); }
    }
    private Path generateFinalReportPath(ScenarioManager.Scenario scenario) throws Exception {
        java.util.Map<String,Path> images=new LinkedHashMap<>();
        if (screenshots!=null) screenshots.captured().forEach((scene,path)->images.put(switch(scene) {
            case HOME -> "home"; case DATA -> "data"; case FLOOD -> "flood"; case DAMAGE -> "damage"; case RISK -> "risk"; case CLOSURE -> "closure";
            case ROUTE -> "route"; case RESOURCES -> "resources"; case REPORT -> "report"; },path));
        Path route=emergencyDispatch==null?null:emergencyDispatch.latestRouteReport();
        Path reportDirectory=Path.of("outputs/final-reports").resolve("report-"+UUID.randomUUID());
        Path validation=new ResultValidator().validate(damageEvidence,riskReport,route,
                reportDirectory.resolve("validation_result.json"));
        if (!json.readTree(validation.toFile()).path("cross_evidence_consistent").asBoolean())
            throw new IllegalStateException("灾损、风险或路线结果复核不一致："+validation);
        finalReport=new ReportGenerator().generate(new ReportGenerator.Evidence(scenario.name(),scenario.simulated(),
                aiEvidence,damageEvidence,riskReport,route,resourceEvidence,floodAreaSquareMetres,images),
                reportDirectory);
        VBox preview=new VBox(6,heading("综合分析报告 · "+scenario.name()),
                new Label("AI："+("REPLAY".equals(scenario.aiMode())?"预测结果回放":"实时推理")),
                new Label(String.format(Locale.ROOT,"灾害区域面积：%.3f km²",floodAreaSquareMetres/1_000_000)),
                new Label("风险等级："+risk.getText()+"　综合指数："+riskScore.getText()),
                new Label("受灾建筑："+floodedBuildings.getText()+"　影响人口："+population.getText()),
                new Label("阻断道路："+blockedRoad.getText()+"　最佳路线："+rescueDistance.getText()),
                new Label("资源方案："+resourceEvidence),new Label("完整 HTML："+finalReport));
        javafx.scene.web.WebView html=new javafx.scene.web.WebView();
        html.getEngine().load(finalReport.toAbsolutePath().toUri().toString());
        html.setPrefHeight(420);
        preview.getChildren().add(html);
        show(preview); return finalReport;
    }
    private void captureLater() {
        javafx.animation.PauseTransition delay = new javafx.animation.PauseTransition(javafx.util.Duration.millis(500));
        delay.setOnFinished(e -> capture());
        delay.play();
    }
    private void capture() {
        try {
            Path directory = Files.createDirectories(evidenceRoot.resolve("workspace-" +
                    LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss-SSS"))));
            WritableImage image = snapshot(new SnapshotParameters(), null);
            BufferedImage pixels = new BufferedImage((int)image.getWidth(),(int)image.getHeight(),BufferedImage.TYPE_INT_ARGB);
            for (int y=0;y<pixels.getHeight();y++) for (int x=0;x<pixels.getWidth();x++)
                pixels.setRGB(x,y,image.getPixelReader().getArgb(x,y));
            ImageIO.write(pixels,"png",directory.resolve("workspace.png").toFile());
            Files.writeString(directory.resolve("run.log"),log.getText(),StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
            java.util.Map<String,Object> manifest = new LinkedHashMap<>();
            manifest.put("map_component","com.zondy.mapgis.controls.MapControl");
            manifest.put("layer_count",map.getLayerCount());
            manifest.put("layers",java.util.stream.IntStream.range(0,map.getLayerCount()).mapToObj(i ->
                    java.util.Map.of("name",map.getLayer(i).getName(),"url",String.valueOf(map.getLayer(i).getURL()),
                            "visible",map.getLayer(i).getState().toString())).toList());
            manifest.put("metrics",java.util.Map.of("buildings",buildings.getText(),"candidate_flooded_buildings",floodedBuildings.getText(),
                    "road_length",roadLength.getText(),"affected_population",population.getText(),"risk",risk.getText(),
                    "rescue_distance",rescueDistance.getText(),"rescue_time",rescueTime.getText(),
                    "rescue_roads",rescueRoads.getText(),"rescue_avoided",rescueAvoided.getText()));
            manifest.put("source",source.getText());
            manifest.put("model_accuracy_verified",false);
            if (thematicManifest != null) manifest.put("damage_thematic_manifest",thematicManifest.toString());
            if (riskReport != null) manifest.put("risk_report",riskReport.toString());
            if (emergencyDispatch != null && emergencyDispatch.latestRouteReport()!=null)
                manifest.put("route_report",emergencyDispatch.latestRouteReport().toString());
            Files.writeString(directory.resolve("evidence.json"),json.writerWithDefaultPrettyPrinter().writeValueAsString(manifest),
                    StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
            appendLog("截图与验证数据已保存：" + directory);
        } catch (Exception error) { fail("保存验收截图",error); }
    }
    @Override public void close() {
        if (inference != null) inference.close();
        if (emergencyDispatch != null) emergencyDispatch.close();
        mapControl.dispose(); map.dispose();
    }
}


