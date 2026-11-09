package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.*;
import com.mapgis.floodguard.report.HtmlOperationalReport;
import com.zondy.mapgis.geodatabase.SFeatureCls;
import com.zondy.mapgis.geodatabase.net.NetCls;
import com.zondy.mapgis.pluginengine.IApplication;
import com.zondy.mapgis.pluginengine.plugin.IMapContentsView;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.stage.FileChooser;
import java.nio.file.*;
import java.util.*;

/** Read-only native scenario routing; all operations stay on the MapGIS host/FX thread. */
public final class DispatchPanel extends VBox {
    public void setLogSink(java.util.function.Consumer<String> sink) {
        status.textProperty().addListener((o,a,b) -> sink.accept("路径/调度：" + b));
    }
    private final ObjectMapper json = new ObjectMapper();
    private final TextArea output = new TextArea();
    private final ComboBox<String> destination = new ComboBox<>(), resourceType = new ComboBox<>();
    private final Spinner<Integer> demand = new Spinner<>(1,Integer.MAX_VALUE,1);
    private final TableView<ResourceDispatcher.Allocation> allocations = new TableView<>();
    private final Label status = new Label("导入真实路网、资源、节点及道路核查JSON。不会修改源路网或实际下发调度。");
    private final Button execute = new Button("计算 MapGIS 阻断避让与分配"), export = new Button("导出业务报告及证据");
    private DispatchRequest request;
    private RoadClosurePlan.Result closures;
    private ResourceDispatcher.DispatchPlan plan;
    private final IApplication application;
    private final SFeatureCls roads;
    private final String roadUrl, provenance;
    private final ExposureAssessment.Result exposure;
    private final Path directory;

    public DispatchPanel(IApplication application, SFeatureCls roads, String roadUrl,
                         ExposureAssessment.Result exposure, Path directory, String provenance) {
        this.application=application; this.roads=roads; this.roadUrl=roadUrl; this.exposure=exposure;
        this.directory=directory; this.provenance=provenance;
        setSpacing(12); setPadding(new Insets(16)); status.setWrapText(true);
        Label heading = new Label("道路核查 · 网络避让 · 资源调度");
        heading.setStyle("-fx-font-size:20px;-fx-font-weight:bold");
        output.setEditable(false); output.setWrapText(true); VBox.setVgrow(output,Priority.ALWAYS);
        allocations.getColumns().add(column("资源",a -> a.recommendation().resource().id()));
        allocations.getColumns().add(column("分配容量",a -> ""+a.assignedCapacity()));
        allocations.getColumns().add(column("预计分钟",a -> ""+a.recommendation().route().estimatedMinutes()));
        allocations.getColumns().add(column("距离 km",a -> ""+a.recommendation().route().distanceKm()));
        allocations.getColumns().add(column("路径边 ID",a -> a.recommendation().route().roadIds().toString()));
        var tabs=new TabPane(new Tab("资源分配",allocations),new Tab("输入与原生结果",output));
        tabs.getTabs().forEach(t -> t.setClosable(false)); VBox.setVgrow(tabs,Priority.ALWAYS);
        destination.valueProperty().addListener((o,a,b) -> invalidatePlan());
        resourceType.valueProperty().addListener((o,a,b) -> invalidatePlan());
        demand.valueProperty().addListener((o,a,b) -> invalidatePlan());
        Button load = new Button("导入调度任务 JSON"); load.setOnAction(e -> load());
        execute.setDisable(true); export.setDisable(true);
        execute.setOnAction(e -> execute()); export.setOnAction(e -> export());
        getChildren().addAll(heading,new HBox(10,load,execute,export),
                new HBox(10,new Label("目的节点"),destination,new Label("资源类型"),resourceType,new Label("需求"),demand),status,tabs);
    }
    private static TableColumn<ResourceDispatcher.Allocation,String> column(String name,java.util.function.Function<ResourceDispatcher.Allocation,String> value) {
        TableColumn<ResourceDispatcher.Allocation,String> column=new TableColumn<>(name);
        column.setCellValueFactory(cell -> new javafx.beans.property.ReadOnlyStringWrapper(value.apply(cell.getValue())));
        column.setPrefWidth(160); return column;
    }
    private void invalidatePlan() { plan=null; closures=null; allocations.getItems().clear(); export.setDisable(true); }
    private void load() {
        FileChooser chooser = new FileChooser(); chooser.setTitle("选择真实调度任务");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("JSON","*.json"));
        var file = chooser.showOpenDialog(getScene().getWindow()); if (file==null) return;
        request=null; invalidatePlan(); execute.setDisable(true); output.clear();
        try {
            if (Files.size(file.toPath())>5_000_000) throw new IllegalArgumentException("任务文件过大");
            request=json.readValue(file,DispatchRequest.class);
            destination.getItems().setAll(new TreeSet<>(request.nodes().keySet())); destination.setValue(request.destination());
            resourceType.getItems().setAll(request.resources().stream().map(ResourceDispatcher.Resource::type).distinct().sorted().toList());
            resourceType.setValue(request.type()); demand.getValueFactory().setValue(request.demand());
            output.setText(json.writerWithDefaultPrettyPrinter().writeValueAsString(request));
            status.setText("已读取资源 "+request.resources().size()+" 项；需求 "+request.demand()+"。请确认资源与道路核查证据仍有效。");
            execute.setDisable(false);
        } catch (Exception error) { fail(error); }
    }
    private void execute() {
        invalidatePlan();
        try {
            request=new DispatchRequest(request.networkUrl(),request.forwardMinutes(),request.reverseMinutes(),request.nodeMinutes(),
                    request.kilometersPerNetworkUnit(),request.nodes(),request.resources(),resourceType.getValue(),destination.getValue(),demand.getValue(),request.reviews());
            if (!(application.getActiveContentsView() instanceof IMapContentsView view))
                throw new IllegalStateException("请激活包含真实网络图层的二维地图");
            NetCls network=null;
            var map=view.getMapControl().getMap();
            for (int i=0;i<map.getLayerCount();i++) {
                if (map.getLayer(i).getData() instanceof NetCls candidate && request.networkUrl().equals(candidate.getURL())) {
                    var sref=map.getLayer(i).getSrefInfo();
                    if (sref==null || !sref.toWkt().startsWith("PROJCS["))
                        throw new IllegalArgumentException("距离计算需要投影坐标网络和明确线性单位，不能把经纬度当公里");
                    if (network!=null) throw new IllegalArgumentException("多个同源网络图层，请保留唯一分析对象");
                    network=candidate;
                }
            }
            if (network==null || !network.hasOpened()) throw new IllegalArgumentException("任务指定的网络未在当前地图打开");
            closures=new RoadClosurePlan().build(exposure,request.reviews(),new MapGisRoadNetworkMapper(network,roads,roadUrl));
            if (closures.unreviewed()>0) throw new IllegalArgumentException("尚有 "+closures.unreviewed()+" 条候选道路未核查，暂不输出调度建议");
            var router=new MapGisNetworkRouter(network,request.nodes(),closures.blockedEdges(),request.forwardMinutes(),
                    request.reverseMinutes(),request.nodeMinutes(),request.kilometersPerNetworkUnit());
            plan=new ResourceDispatcher().plan(request.resources(),request.type(),request.destination(),request.demand(),router);
            allocations.getItems().setAll(plan.allocations());
            output.setText(json.writerWithDefaultPrettyPrinter().writeValueAsString(Map.of("road_network",closures,"dispatch",plan)));
            status.setText("原生计算已返回；阻断网络边 "+closures.blockedEdges().size()+"，分配资源 "+plan.allocations().size()
                    +"，未满足需求 "+plan.unfulfilled()+"。这是建议，不是实际指令或现实安全保证。");
            export.setDisable(false);
        } catch (Exception | LinkageError error) { fail(error); }
    }
    private void export() {
        try {
            Path manifestPath=directory.resolve("spatial-result.json");
            if (!Files.isRegularFile(manifestPath) || Files.size(manifestPath)>16_000_000)
                throw new IllegalArgumentException("缺少完整空间结果清单，不能输出可追溯报告包");
            var manifest=json.readTree(manifestPath.toFile());
            String inference=new com.mapgis.floodguard.report.HtmlInferenceReport().render("洪涝事件",
                    Path.of(manifest.path("pre_image").asText()),Path.of(manifest.path("post_image").asText()),manifest.path("model_result"));
            // Isolated bundle prevents partial writes from masquerading as a complete report.
            Path bundle=Files.createDirectory(directory.resolve("dispatch-"+UUID.randomUUID()));
            Files.writeString(bundle.resolve("evidence.json"),json.writerWithDefaultPrettyPrinter().writeValueAsString(
                    Map.of("request",request,"exposure",exposure,"roads",closures,"plan",plan,"provenance",provenance,"spatial_manifest",manifest)),StandardOpenOption.CREATE_NEW);
            Files.writeString(bundle.resolve("inference.html"),inference,StandardOpenOption.CREATE_NEW);
            String report=new HtmlOperationalReport().render(exposure,closures,plan,request,provenance)
                    .replace("</html>","<p><a href='inference.html'>原始模型版本、像素统计与内嵌预览</a> · <a href='evidence.json'>完整输入与结果证据</a></p></html>");
            Files.writeString(bundle.resolve("report.html"),report,StandardOpenOption.CREATE_NEW);
            status.setText("已保存业务报告和原始输入/结果："+bundle);
        } catch (Exception error) { fail(error); }
    }
    private void fail(Throwable error) { error.printStackTrace(System.err); status.setText("未完成："+error.getMessage()); }
}
