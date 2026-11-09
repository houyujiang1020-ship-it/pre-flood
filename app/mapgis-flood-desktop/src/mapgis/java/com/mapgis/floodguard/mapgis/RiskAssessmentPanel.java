package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.zondy.mapgis.att.Record;
import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.controls.SelectItem;
import com.zondy.mapgis.geodatabase.SFeatureCls;
import com.zondy.mapgis.geometry.Dot;
import com.zondy.mapgis.map.MapLayer;
import com.zondy.mapgis.map.VectorLayer;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.input.MouseButton;
import javafx.scene.input.MouseEvent;
import javafx.scene.layout.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;

/** Inputs, native overlay execution, zone inspection, and acceptance evidence. */
public final class RiskAssessmentPanel extends VBox {
    private static final List<String> ROLES=List.of("行政区域","人口格网","真实洪水面","正常建筑","受淹建筑","正常道路","受影响道路","阻断道路","原始道路");
    private final MapControl control;
    private final Path evidenceRoot;
    private final Consumer<String> log;
    private final Consumer<FloodRiskAssessment.Result> completed;
    private final Consumer<FloodRiskAssessment.AreaResult> selectedArea;
    private final Runnable capture;
    private final Map<String,ComboBox<VectorLayer>> selectors=new LinkedHashMap<>();
    private final TextField areaField=new TextField("area_name");
    private final TextField resourceField=new TextField("resource_distance_risk");
    private final TextField roadLedgerField=new TextField();
    private final TextField originalRoadsField=new TextField();
    private final Label status=new Label("选择 MapGIS 原生图层，执行行政区叠加分析。");
    private final TextArea details=new TextArea("点击风险分区查看属性。");
    private final Button execute=new Button("执行风险评估并生成专题图");
    private final ObjectMapper json=new ObjectMapper();
    private List<VectorLayer> riskLayers=List.of();
    private FloodRiskAssessment.Result lastAssessment;
    private MapGisRiskThematicWriter.Result lastThematic;

    public RiskAssessmentPanel(MapControl control,Path evidenceRoot,Consumer<String> log,
                               Consumer<FloodRiskAssessment.Result> completed,
                               Consumer<FloodRiskAssessment.AreaResult> selectedArea,Runnable capture) {
        this.control=control; this.evidenceRoot=evidenceRoot; this.log=log; this.completed=completed;
        this.selectedArea=selectedArea; this.capture=capture;
        setPadding(new Insets(12)); setSpacing(8);
        Label title=new Label("洪涝风险评估 · MapGIS 原生空间叠加与风险分区");
        title.setStyle("-fx-font-size:18px;-fx-font-weight:bold;");
        GridPane grid=new GridPane(); grid.setHgap(8); grid.setVgap(5);
        for (int i=0;i<ROLES.size();i++) {
            String role=ROLES.get(i); ComboBox<VectorLayer> selector=new ComboBox<>(); selector.setPrefWidth(250);
            selector.setCellFactory(v->layerCell()); selector.setButtonCell(layerCell()); selectors.put(role,selector);
            grid.add(new Label(role),i%2*2,i/2); grid.add(selector,i%2*2+1,i/2);
        }
        selectors.get("原始道路").valueProperty().addListener((value,oldLayer,newLayer)->{
            if (newLayer!=null) originalRoadsField.setText(String.valueOf(newLayer.getURL()));
        });
        Button refresh=new Button("刷新 MapGIS 图层"); refresh.setOnAction(e->refreshLayers());
        execute.setOnAction(e->run());
        status.setWrapText(true); details.setEditable(false); details.setPrefRowCount(7);
        getChildren().addAll(title,new Label("人口风险仅使用真实洪水面；缺失时输出部分报告，不计算综合分数。"),grid,
                new HBox(8,new Label("区域名称字段"),areaField,new Label("资源距离风险字段"),resourceField),
                new HBox(8,new Label("道路状态核查单"),roadLedgerField,new Label("原始道路 gdbp URL"),originalRoadsField),
                new HBox(8,refresh,execute),new Label("低风险：绿　中风险：黄　高风险：红　数据不完整：灰"),status,new Label("区域属性"),details);
        control.addEventFilter(MouseEvent.MOUSE_CLICKED,event->{
            if (event.getButton()==MouseButton.PRIMARY && !riskLayers.isEmpty()) inspect(event);
        });
        refreshLayers();
    }
    private static ListCell<VectorLayer> layerCell() {
        return new ListCell<>() { @Override protected void updateItem(VectorLayer value,boolean empty) {
            super.updateItem(value,empty); setText(empty||value==null?"—":value.getName()+" · "+value.getURL());
        }};
    }
    public void refreshLayers() {
        List<VectorLayer> available=new ArrayList<>();
        for (int i=0;i<control.getMap().getLayerCount();i++) {
            MapLayer layer=control.getMap().getLayer(i);
            if (layer instanceof VectorLayer vector && vector.getData() instanceof SFeatureCls) available.add(vector);
        }
        for (String role:ROLES) {
            ComboBox<VectorLayer> box=selectors.get(role); VectorLayer prior=box.getValue();
            box.getItems().setAll(available);
            if (prior!=null && available.contains(prior)) box.setValue(prior);
            else {
                String cue=switch(role) {
                    case "行政区域" -> "行政"; case "人口格网" -> "人口"; case "真实洪水面" -> "洪水面";
                    case "正常建筑" -> "未受淹建筑"; case "受淹建筑" -> "受淹建筑";
                    case "正常道路" -> "正常道路"; case "受影响道路" -> "受影响道路";
                    case "原始道路" -> "原始道路";
                    default -> "阻断道路";
                };
                available.stream().filter(l->l.getName().contains(cue)).findFirst().ifPresent(box::setValue);
            }
        }
    }
    public void autoRunWhenReady() {
        refreshLayers();
        if (List.of("行政区域","人口格网","真实洪水面","正常建筑","受淹建筑","正常道路","阻断道路","原始道路")
                .stream().allMatch(role->selectors.get(role).getValue()!=null) && lastAssessment==null) run();
    }
    public FloodRiskAssessment.Result runScenario(String areaFieldName,String resourceFieldName,
                                                  Path roadLedger,String originalRoadsUrl,String caseMode) throws Exception {
        refreshLayers(); areaField.setText(areaFieldName); resourceField.setText(resourceFieldName);
        roadLedgerField.setText(roadLedger.toString()); originalRoadsField.setText(originalRoadsUrl);
        var input=new FloodRiskAssessment.Inputs(selected("行政区域"),selected("人口格网"),selected("真实洪水面"),
                selected("正常建筑"),selected("受淹建筑"),selected("正常道路"),selected("受影响道路"),
                selected("阻断道路"),selected("原始道路"),areaFieldName,resourceFieldName,roadLedger,originalRoadsUrl,caseMode);
        var assessment=new FloodRiskAssessment().assess(input,evidenceRoot);
        if (assessment.areas().stream().anyMatch(a->a.riskScore()==null))
            throw new IllegalStateException("风险评估缺少完整指标："+assessment.reportJson());
        var thematic=new MapGisRiskThematicWriter().write(control,input,assessment);
        for (VectorLayer old:riskLayers) control.getMap().remove(old);
        riskLayers=thematic.layers(); lastAssessment=assessment; lastThematic=thematic;
        control.refreshWnd(); completed.accept(assessment); log.accept("案例风险分区已生成："+assessment.reportJson());
        return assessment;
    }
    public void bindScenarioSources(String areasUrl,String populationUrl,String floodUrl,
                                    String normalBuildingsUrl,String floodedBuildingsUrl,
                                    String normalRoadsUrl,String floodedRoadsUrl,String blockedRoadsUrl,String originalRoadsUrl) {
        clearPreviousAssessment(); refreshLayers();
        java.util.Map<String,String> urls=java.util.Map.of("行政区域",areasUrl,"人口格网",populationUrl,
                "真实洪水面",floodUrl,"正常建筑",normalBuildingsUrl,"受淹建筑",floodedBuildingsUrl,
                "正常道路",normalRoadsUrl,"阻断道路",blockedRoadsUrl,"原始道路",originalRoadsUrl);
        urls.forEach((role,url)->{
            VectorLayer exact=selectors.get(role).getItems().stream().filter(layer->url.equals(String.valueOf(layer.getURL())))
                    .findFirst().orElseThrow(()->new IllegalArgumentException("案例图层未在 MapGIS 地图中加载："+role+" · "+url));
            selectors.get(role).setValue(exact);
        });
        VectorLayer affected=selectors.get("受影响道路").getItems().stream()
                .filter(layer->floodedRoadsUrl.equals(String.valueOf(layer.getURL())))
                .findFirst().orElseThrow(()->new IllegalArgumentException("案例受淹道路图层未加载："+floodedRoadsUrl));
        selectors.get("受影响道路").setValue(affected);
    }
    private VectorLayer selected(String role) { return selectors.get(role).getValue(); }
    private void clearPreviousAssessment() {
        for (VectorLayer layer:riskLayers) control.getMap().remove(layer);
        riskLayers=List.of(); lastAssessment=null; lastThematic=null;
        details.setText("案例已切换；请重新计算风险。"); control.refreshWnd();
    }
    private void run() {
        if (execute.isDisabled()) return;
        execute.setDisable(true);
        status.setText("MapGIS 空间叠加分析中……");
        try {
            var input=new FloodRiskAssessment.Inputs(selected("行政区域"),selected("人口格网"),selected("真实洪水面"),
                    selected("正常建筑"),selected("受淹建筑"),selected("正常道路"),selected("受影响道路"),
                    selected("阻断道路"),selected("原始道路"),areaField.getText().trim(),resourceField.getText().trim(),
                    roadLedgerField.getText().isBlank()?null:Path.of(roadLedgerField.getText().trim()),
                    originalRoadsField.getText().trim(),"UNSPECIFIED");
            var assessment=new FloodRiskAssessment().assess(input,evidenceRoot);
            var thematic=new MapGisRiskThematicWriter().write(control,input,assessment);
            for (VectorLayer old:riskLayers) control.getMap().remove(old);
            control.refreshWnd();
            riskLayers=thematic.layers(); lastAssessment=assessment; lastThematic=thematic;
            completed.accept(assessment);
            long complete=assessment.areas().stream().filter(a->a.riskScore()!=null).count();
            status.setText("已评估 "+assessment.areas().size()+" 个区域；四项指标完整 "+complete+
                    " 个（案例尚未现场验收）。报告："+assessment.reportJson()+"；专题图："+thematic.manifest());
            log.accept("风险评估完成；完整区域="+complete+"；JSON="+assessment.reportJson()+"；HTML="+assessment.reportHtml());
            capture.run();
        } catch (Exception | LinkageError error) {
            error.printStackTrace(System.err);
            status.setText("风险评估未完成："+error.getMessage()); log.accept("风险评估异常："+error.getMessage());
        } finally { execute.setDisable(false); }
    }
    private void inspect(MouseEvent event) {
        try {
            Dot location=control.localToLocation(event.getX(),event.getY()); if (location==null) return;
            for (int i=riskLayers.size()-1;i>=0;i--) {
                VectorLayer layer=riskLayers.get(i); List<SelectItem> hits=control.identifySelections(location,layer);
                if (hits==null || hits.isEmpty()) continue;
                SelectItem hit=hits.get(0); Record record=((SFeatureCls)layer.getData()).getAtt(hit.getOid());
                if (record==null) throw new IllegalStateException("MapGIS 风险属性读取失败");
                try {
                    StringBuilder info=new StringBuilder(); Map<String,Object> selected=new LinkedHashMap<>();
                    selected.put("mapgis_oid",hit.getOid()); selected.put("layer_url",layer.getURL());
                    String areaId=String.valueOf(record.getFieldVal("area_id"));
                    var result=lastAssessment.areas().stream().filter(a->a.areaId().equals(areaId)).findFirst()
                            .orElseThrow(()->new IllegalStateException("专题图区域 ID 与报告不一致："+areaId));
                    selected.put("area_id",result.areaId()); selected.put("area_name",result.area());
                    selected.put("status",result.status()); selected.put("risk_level",result.riskLevel());
                    selected.put("risk_score",result.riskScore()); selected.put("building_risk",result.buildingRisk());
                    selected.put("population_risk",result.populationRisk()); selected.put("road_risk",result.roadRisk());
                    selected.put("resource_risk",result.resourceDistanceRisk()); selected.put("reason",result.reason());
                    for (var entry:selected.entrySet()) info.append(entry.getKey()).append("：")
                            .append(entry.getValue()==null?"—":entry.getValue()).append('\n');
                    details.setText(info.toString());
                    selectedArea.accept(result);
                    Path file=lastAssessment.directory().resolve("selected-risk-area-"+UUID.randomUUID()+".json");
                    selected.put("risk_report",lastAssessment.reportJson().toString());
                    selected.put("thematic_manifest",lastThematic.manifest().toString());
                    Files.writeString(file,json.writerWithDefaultPrettyPrinter().writeValueAsString(selected),StandardOpenOption.CREATE_NEW);
                    log.accept("风险区域点击查询："+selected.get("area_name")+"；证据="+file); capture.run();
                } finally { record.dispose(); }
                return;
            }
            details.setText("该位置没有已生成的风险分区。");
        } catch (Exception | LinkageError error) {
            error.printStackTrace(System.err); details.setText("区域查询失败："+error.getMessage());
            log.accept("风险区域查询异常："+error.getMessage());
        }
    }
}
