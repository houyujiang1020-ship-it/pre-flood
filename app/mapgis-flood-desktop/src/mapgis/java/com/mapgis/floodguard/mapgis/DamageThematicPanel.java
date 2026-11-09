package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.zondy.mapgis.att.Record;
import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.controls.SelectItem;
import com.zondy.mapgis.geodatabase.SFeatureCls;
import com.zondy.mapgis.geometry.Dot;
import com.zondy.mapgis.map.VectorLayer;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.input.MouseButton;
import javafx.scene.input.MouseEvent;
import javafx.scene.layout.*;
import javafx.stage.FileChooser;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;

/** Native thematic map import and object inspection for flood_prediction.json. */
public final class DamageThematicPanel extends VBox {
    private final MapControl control;
    private final Path evidenceRoot;
    private final Consumer<String> log;
    private final Consumer<MapGisDamageThematicImporter.Result> loaded;
    private final Label status = new Label("选择带米制投影 crs_wkt 的 flood_prediction.json。");
    private final TextArea details = new TextArea("点击已加载的专题对象查看属性。");
    private final MapGisDamageThematicImporter importer = new MapGisDamageThematicImporter();
    private List<VectorLayer> thematicLayers = List.of();
    private Path lastInput;
    private MapGisDamageThematicImporter.Result lastRun;
    private final Runnable captureEvidence;
    private final ObjectMapper json = new ObjectMapper();

    public DamageThematicPanel(MapControl control, Path evidenceRoot, Consumer<String> log,
                               Consumer<MapGisDamageThematicImporter.Result> loaded, Runnable captureEvidence) {
        this.control = control; this.evidenceRoot = evidenceRoot; this.log = log; this.loaded = loaded;
        this.captureEvidence = captureEvidence;
        setPadding(new Insets(12)); setSpacing(10);
        Label title = new Label("灾损专题地图 · MapGIS 原生图层");
        title.setStyle("-fx-font-size:18px;-fx-font-weight:bold;");
        status.setWrapText(true); details.setEditable(false); details.setPrefRowCount(7);
        Button choose = new Button("加载 flood_prediction.json");
        choose.setOnAction(e -> chooseFile());
        Button reload = new Button("重新加载当前文件");
        reload.setOnAction(e -> { if (lastInput != null) importFile(lastInput); });
        Label legend = new Label("● 受淹建筑：红色　● 未受淹建筑：绿色　━━ 阻断道路：红色粗线　─ 正常道路：灰色线");
        legend.setWrapText(true);
        getChildren().addAll(title,new HBox(8,choose,reload),legend,status,new Label("点击对象属性"),details);
        control.addEventFilter(MouseEvent.MOUSE_CLICKED, event -> {
            if (event.getButton() == MouseButton.PRIMARY && !thematicLayers.isEmpty()) inspect(event);
        });
    }
    public void autoLoad(Path file) {
        if (Files.isRegularFile(file) && lastInput == null) importFile(file);
    }
    private void chooseFile() {
        FileChooser chooser = new FileChooser(); chooser.setTitle("选择 AI 对象灾损结果");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("JSON","*.json"));
        if (lastInput != null && Files.isRegularFile(lastInput)) chooser.setInitialDirectory(lastInput.getParent().toFile());
        var chosen = chooser.showOpenDialog(getScene().getWindow());
        if (chosen != null) importFile(chosen.toPath());
    }
    private void importFile(Path file) {
        status.setText("正在用 MapGIS SDK 写入对象要素并加载专题图层……");
        try {
            var result = importer.importAndLoad(control,file,evidenceRoot);
            for (VectorLayer old : thematicLayers) control.getMap().remove(old);
            control.refreshWnd();
            thematicLayers = result.layers(); lastInput = file; lastRun = result;
            loaded.accept(result);
            int total = result.counts().values().stream().mapToInt(Integer::intValue).sum();
            status.setText("已加载 " + total + " 个对象、4 个 MapGIS 专题图层；证据：" + result.manifest());
            log.accept("灾损专题导入完成：" + result.manifest());
        } catch (Exception | LinkageError error) {
            error.printStackTrace(System.err);
            status.setText("专题图层未完成：" + error.getMessage());
            log.accept("灾损专题导入失败：" + error.getMessage());
        }
    }
    private void inspect(MouseEvent event) {
        try {
            Dot location = control.localToLocation(event.getX(),event.getY());
            if (location == null) return;
            for (int i=thematicLayers.size()-1;i>=0;i--) {
                VectorLayer layer = thematicLayers.get(i);
                List<SelectItem> hits = control.identifySelections(location,layer);
                if (hits == null || hits.isEmpty()) continue;
                SelectItem hit = hits.get(0);
                if (!(layer.getData() instanceof SFeatureCls cls)) throw new IllegalStateException("专题对象数据源已断开");
                Record record = cls.getAtt(hit.getOid());
                if (record == null) throw new IllegalStateException("对象属性读取失败："+hit.getOid());
                try {
                    String type = String.valueOf(record.getFieldVal("object_type"));
                    String area = "building".equals(type) ? value(record,"area_m2") + " m²" : "道路不适用";
                    String length = "road".equals(type) ? value(record,"length_m") + " m" : "建筑不适用";
                    details.setText("对象编号："+value(record,"object_id")+"\n类型："+type+
                            "\n状态："+value(record,"flood_status")+"\n面积："+area+
                            "\n道路长度："+length+"\n受灾等级："+value(record,"severity")+
                            "\n损伤概率："+value(record,"damage_probability")+
                            "\n坐标（外包矩形中心，源投影）："+value(record,"x")+", "+value(record,"y")+
                            "\nMapGIS OID："+hit.getOid());
                    java.util.Map<String,Object> evidence = new java.util.LinkedHashMap<>();
                    evidence.put("source_manifest",lastRun.manifest().toString());
                    evidence.put("mapgis_oid",hit.getOid()); evidence.put("layer_url",layer.getURL());
                    for (String key : List.of("object_id","object_type","flood_status","area_m2","length_m",
                            "damage_probability","severity","x","y")) evidence.put(key,value(record,key));
                    Path item = lastRun.directory().resolve("selected-object-"+UUID.randomUUID()+".json");
                    Files.writeString(item,json.writerWithDefaultPrettyPrinter().writeValueAsString(evidence),
                            StandardOpenOption.CREATE_NEW);
                    log.accept("已识别专题对象："+value(record,"object_id")+"；证据："+item);
                    captureEvidence.run();
                } finally { record.dispose(); }
                return;
            }
            details.setText("该位置没有当前灾损专题对象。");
        } catch (Exception | LinkageError error) {
            error.printStackTrace(System.err);
            details.setText("对象识别失败："+error.getMessage());
            log.accept("专题对象识别异常："+error.getMessage());
        }
    }
    private static String value(Record record,String name) {
        Object value = record.getFieldVal(name);
        return value == null ? "—" : value.toString();
    }
}
