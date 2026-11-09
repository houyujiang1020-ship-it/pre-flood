package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.*;
import com.mapgis.floodguard.report.HtmlExposureReport;
import com.zondy.mapgis.geodatabase.SFeatureCls;
import com.zondy.mapgis.geometry.Geometry;
import com.zondy.mapgis.map.VectorLayer;
import com.zondy.mapgis.pluginengine.IApplication;
import com.zondy.mapgis.pluginengine.plugin.IMapContentsView;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import java.nio.file.*;
import java.util.*;

/** Read-only exposure queries against user-selected MapGIS entity layers. */
public final class ExposurePanel extends VBox {
    private java.util.function.Consumer<String> logSink = message -> {};
    private java.util.function.BiConsumer<Long,ExposureAssessment.Result> assessmentSink = (total, result) -> {};
    private java.util.function.Consumer<DispatchPanel> dispatchSink;
    public void setLogSink(java.util.function.Consumer<String> sink) {
        logSink = sink; status.textProperty().addListener((o,a,b) -> sink.accept("GIS分析：" + b));
    }
    public void setAssessmentSink(java.util.function.BiConsumer<Long,ExposureAssessment.Result> sink) { assessmentSink = sink; }
    public void setDispatchSink(java.util.function.Consumer<DispatchPanel> sink) { dispatchSink = sink; }
    public DispatchPanel createDispatchPanel() {
        if (assessment == null || roads.getValue() == null) throw new IllegalStateException("请先完成建筑/道路实体核查");
        return new DispatchPanel(application, (SFeatureCls)roads.getValue().layer().getData(),
                identity(roads.getValue()), assessment, patches.getParent(), sourceDescription);
    }
    private record LayerChoice(VectorLayer layer, String name) { @Override public String toString() { return name; } }
    private final ComboBox<LayerChoice> buildings = new ComboBox<>(), roads = new ComboBox<>();
    private final TextArea results = new TextArea();
    private final IApplication application;
    private final Path mask;
    private final Path patches;
    private final java.util.function.Supplier<Path> activeMask;
    private final Label status = new Label("请选择实体图层；不会修改源数据。相交只表示候选暴露，不等于损毁或阻断。");
    private final Button save = new Button("导出实体核查报告");
    private final Button dispatch = new Button("道路核查与资源调度");
    private ExposureAssessment.Result assessment;
    private String sourceDescription;

    public ExposurePanel(IApplication application, Path mask, Path patches) {
        this(application,mask,patches,() -> mask);
    }
    public ExposurePanel(IApplication application, Path mask, Path patches,
                         java.util.function.Supplier<Path> activeMask) {
        this.application = application; this.mask = mask; this.patches = patches;
        this.activeMask = activeMask;
        setPadding(new Insets(16)); setSpacing(12);
        Label heading = new Label("建筑与道路实体暴露核查");
        heading.setStyle("-fx-font-size:20px;-fx-font-weight:bold");
        status.setWrapText(true); results.setEditable(false); results.setWrapText(true);
        VBox.setVgrow(results, Priority.ALWAYS);
        Button importExercise = new Button("一键导入演练实体");
        Button refresh = new Button("刷新当前地图图层"), run = new Button("执行 MapGIS 相交查询");
        importExercise.setOnAction(e -> importExercise());
        refresh.setOnAction(e -> refresh()); run.setOnAction(e -> run());
        save.setDisable(true); save.setOnAction(e -> save());
        dispatch.setDisable(true); dispatch.setOnAction(e -> {
            if (dispatchSink != null) { dispatchSink.accept(createDispatchPanel()); return; }
            var stage = new javafx.stage.Stage(); stage.initOwner(getScene().getWindow());
            stage.setTitle("MapGIS-FloodGuard · 应急调度");
            stage.setScene(new javafx.scene.Scene(new DispatchPanel(application,(SFeatureCls)roads.getValue().layer().getData(),
                    identity(roads.getValue()),assessment,patches.getParent(),sourceDescription),1000,700)); stage.show();
        });
        buildings.setMaxWidth(Double.MAX_VALUE); roads.setMaxWidth(Double.MAX_VALUE);
        buildings.valueProperty().addListener((o,a,b) -> invalidate());
        roads.valueProperty().addListener((o,a,b) -> invalidate());
        getChildren().addAll(heading, new Label("建筑实体图层（面）"), buildings,
                new Label("道路实体图层（线）"), roads, new HBox(10,importExercise,refresh,run,save,dispatch), status, results);
        refresh();
    }
    private void invalidate() { assessment = null; assessmentSink.accept(null, null); save.setDisable(true); dispatch.setDisable(true); results.clear(); }
    private void importExercise() {
        Path source = null;
        try {
            var chooser=new javafx.stage.DirectoryChooser(); chooser.setTitle("选择包含 manifest.json、buildings.geojson 和 roads.geojson 的演练目录");
            java.io.File selected=chooser.showDialog(getScene().getWindow()); if(selected==null) return;
            source=selected.toPath().toAbsolutePath();
            status.setText("正在创建 MapGIS 演练实体数据库……");
            var imported=new MapGisExerciseEntityImporter().importAndLoad(application,source);
            refresh();
            boolean buildingVisible=buildings.getItems().stream().anyMatch(layer -> imported.buildingsUrl().equals(layer.layer().getURL()));
            boolean roadVisible=roads.getItems().stream().anyMatch(layer -> imported.roadsUrl().equals(layer.layer().getURL()));
            if (!buildingVisible || !roadVisible)
                throw new IllegalStateException("MapGIS 地图未同时显示已导入的建筑面和道路线图层");
            buildings.setValue(buildings.getItems().stream()
                    .filter(layer -> imported.buildingsUrl().equals(layer.layer().getURL())).findFirst().orElseThrow());
            roads.setValue(roads.getItems().stream()
                    .filter(layer -> imported.roadsUrl().equals(layer.layer().getURL())).findFirst().orElseThrow());
            status.setText("已导入并加载演练实体：建筑 "+imported.buildings()+"，道路 "+imported.roads()+"，数据库 "+imported.database()+"。请选择两个图层后执行查询。");
        } catch(Exception | LinkageError error) {
            var stack=new java.io.StringWriter(); error.printStackTrace(new java.io.PrintWriter(stack));
            System.err.println("演练实体导入失败；case="+source+"；thread="+Thread.currentThread().getName()+"\n"+stack);
            logSink.accept("演练实体导入异常；case="+source+"；thread="+Thread.currentThread().getName()+"\n"+stack);
            status.setText("导入演练实体失败："+error.getMessage());
        }
    }
    private void refresh() {
        invalidate(); buildings.getItems().clear(); roads.getItems().clear();
        try {
            if (!(application.getActiveContentsView() instanceof IMapContentsView view))
                throw new IllegalStateException("请激活二维地图，并加载建筑面与道路线数据");
            var map = view.getMapControl().getMap();
            for (int i=0; i<map.getLayerCount(); i++) {
                if (map.getLayer(i) instanceof VectorLayer layer && layer.getData() instanceof SFeatureCls features) {
                    String type = features.getGeomType().toString();
                    LayerChoice choice = new LayerChoice(layer, layer.getName() + " [" + type + "]");
                    // SDK enum names checked in this installed version; do not silently infer roles from names.
                    if (features.getGeomType() == com.zondy.mapgis.geometry.GeomType.GeomReg) buildings.getItems().add(choice);
                    if (features.getGeomType() == com.zondy.mapgis.geometry.GeomType.GeomLin) roads.getItems().add(choice);
                }
            }
            status.setText("已读取当前地图顶层实体图层。必须明确选择建筑面和道路线，不会自动把模型斑块当作建筑。");
        } catch (Exception | LinkageError error) { status.setText("读取图层失败：" + error.getMessage()); }
    }
    private void run() {
        invalidate();
        Map<String,Geometry> geometries = new LinkedHashMap<>();
        try {
            LayerChoice building = buildings.getValue(), road = roads.getValue();
            if (building == null || road == null) throw new IllegalArgumentException("请选择建筑面与道路线图层");
            if (activeMask.get()==null || !mask.toAbsolutePath().normalize().equals(activeMask.get().toAbsolutePath().normalize()))
                throw new IllegalStateException("案例影像已切换；当前核查窗口绑定旧洪水掩膜，请从新空间结果重新打开");
            var grid = new MapGisRasterSpatializer().inspect(mask);
            logSpatialInput("建筑",building,grid);
            logSpatialInput("道路",road,grid);
            boolean buildingSameCrs=MapGisExposureQuery.sameCrs(crs(building),grid.crs());
            boolean roadSameCrs=MapGisExposureQuery.sameCrs(crs(road),grid.crs());
            logSink.accept("实体相交预检：建筑 CRS 等价="+buildingSameCrs+"；道路 CRS 等价="+roadSameCrs);
            if (!buildingSameCrs || !roadSameCrs)
                throw new IllegalArgumentException("实体与洪水影像 CRS 不一致；未执行相交查询");
            requireOverlap((SFeatureCls)building.layer().getData(),grid,"建筑");
            requireOverlap((SFeatureCls)road.layer().getData(),grid,"道路");
            if (Files.size(patches) > 50_000_000) throw new IllegalArgumentException("斑块文件过大，请分区处理");
            var json = new ObjectMapper().readTree(patches.toFile());
            if (!"FeatureCollection".equals(json.path("type").asText()) || !json.path("features").isArray())
                throw new IllegalArgumentException("无效斑块结果");
            int index = 0;
            for (var feature : json.path("features")) {
                GeoJsonPatchValidator.validate(feature.path("geometry"),grid);
                Geometry geometry = Geometry.fromGeoJson(feature.path("geometry").toString());
                if (geometry == null) throw new IllegalStateException("MapGIS无法读取斑块几何");
                geometries.put(Integer.toString(++index),geometry);
            }
            var query = new MapGisExposureQuery();
            var hits = new ArrayList<ExposureAssessment.Hit>();
            hits.addAll(query.query((SFeatureCls)building.layer().getData(), identity(building), ExposureAssessment.Kind.BUILDING,
                    crs(building), grid.crs(), geometries));
            hits.addAll(query.query((SFeatureCls)road.layer().getData(), identity(road), ExposureAssessment.Kind.ROAD,
                    crs(road), grid.crs(), geometries));
            assessment = new ExposureAssessment().aggregate(hits);
            sourceDescription = "MapGIS ModeIntersect；建筑=" + identity(building) + "；道路=" + identity(road) + "；斑块=" + patches;
            results.setText(new ObjectMapper().writerWithDefaultPrettyPrinter().writeValueAsString(assessment));
            status.setText("候选建筑实体 " + assessment.candidateBuildings() + "，候选道路实体 " + assessment.candidateRoads()
                    + "；按实体ID去重。道路阻断、受损程度、面积和人口尚未计算。");
            assessmentSink.accept(((SFeatureCls)building.layer().getData()).getObjCount(), assessment);
            save.setDisable(false);
            dispatch.setDisable(false);
        } catch (Exception | LinkageError error) { error.printStackTrace(System.err); status.setText("实体核查失败："+error.getMessage()); }
        finally { geometries.values().forEach(Geometry::dispose); }
    }
    private static String identity(LayerChoice choice) {
        String url = choice.layer().getURL();
        if (url == null || url.isBlank()) throw new IllegalArgumentException("实体图层缺少可追溯数据源URL");
        return url;
    }
    private static String crs(LayerChoice choice) {
        if (choice.layer().getSrefInfo() == null) throw new IllegalArgumentException("实体图层缺少空间参考");
        return choice.layer().getSrefInfo().toWkt();
    }
    private static void requireOverlap(SFeatureCls features, RasterGrid grid, String role) {
        var bounds=features.getRange();
        if (bounds==null || !bounds.isValid()) throw new IllegalArgumentException(role+"图层缺少有效范围");
        if (bounds.getXMax()<grid.x() || bounds.getXMin()>grid.x()+grid.width()*grid.dx()
                || bounds.getYMax()<grid.y()+grid.height()*grid.dy() || bounds.getYMin()>grid.y())
            throw new IllegalArgumentException(role+"图层与当前洪水影像范围不相交；请使用同一场景的配准影像和实体");
    }
    private void logSpatialInput(String role, LayerChoice choice, RasterGrid grid) {
        var bounds=((SFeatureCls)choice.layer().getData()).getRange();
        boolean overlaps=bounds!=null && bounds.isValid() &&
                bounds.getXMax()>=grid.x() && bounds.getXMin()<=grid.x()+grid.width()*grid.dx() &&
                bounds.getYMax()>=grid.y()+grid.height()*grid.dy() && bounds.getYMin()<=grid.y();
        logSink.accept("实体相交预检：洪水栅格="+mask.toAbsolutePath()+"；CRS="+grid.crs()
                +"；范围=["+grid.x()+","+(grid.y()+grid.height()*grid.dy())+","
                +(grid.x()+grid.width()*grid.dx())+","+grid.y()+"]；"+role+" URL="+identity(choice)
                +"；CRS="+crs(choice)+"；范围="+(bounds==null?"MISSING":"["+bounds.getXMin()+","
                +bounds.getYMin()+","+bounds.getXMax()+","+bounds.getYMax()+"]")
                +"；坐标值范围相交="+overlaps+"（须另核对 CRS 等价）");
    }
    private void save() {
        try {
            Path file = patches.resolveSibling("entity-exposure-"+UUID.randomUUID()+".html");
            Files.writeString(file,new HtmlExposureReport().render("洪涝事件",assessment,sourceDescription),
                    java.nio.charset.StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
            status.setText("核查报告已保存："+file);
        } catch (Exception error) { status.setText("导出失败："+error.getMessage()); }
    }
}
