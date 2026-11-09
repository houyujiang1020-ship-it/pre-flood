package com.mapgis.floodguard.mapgis;

import com.mapgis.floodguard.business.ScenarioManager;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import java.nio.file.Path;
import java.util.*;
import java.util.function.Consumer;

/** Case creation, loading and deletion without touching source data. */
public final class ScenarioPanel extends VBox {
    private static final LinkedHashMap<String,String> LABELS=new LinkedHashMap<>();
    static {
        LABELS.put("preImage","灾前影像"); LABELS.put("postImage","灾后影像");
        LABELS.put("predictionJson","对象预测 JSON"); LABELS.put("administrativeUrl","行政区域 MapGIS URL");
        LABELS.put("populationUrl","人口格网 MapGIS URL"); LABELS.put("floodExtentUrl","真实洪水面 MapGIS URL");
        LABELS.put("networkUrl","原生路网 MapGIS URL"); LABELS.put("sourceRoadsUrl","源道路 MapGIS URL");
        LABELS.put("resourceManifest","资源库清单"); LABELS.put("roadStatusLedger","道路状态核查单");
        LABELS.put("startResourceId","救援车辆编号"); LABELS.put("targetResourceId","避难点/医疗点编号");
        LABELS.put("areaNameField","区域名称字段"); LABELS.put("resourceRiskField","资源距离风险字段");
    }
    private final ScenarioManager manager;
    private final Consumer<ScenarioManager.Scenario> loaded;
    private final Consumer<String> log;
    private final ComboBox<Path> cases=new ComboBox<>();
    private final TextField name=new TextField("城市洪涝灾害模拟案例01"),speed=new TextField("30");
    private final ComboBox<String> aiMode=new ComboBox<>();
    private final CheckBox simulated=new CheckBox("模拟演练数据");
    private final Map<String,TextField> fields=new LinkedHashMap<>();
    private final Label status=new Label("创建或加载案例；缺失输入会在一键演练前明确列出。");

    public ScenarioPanel(ScenarioManager manager,Consumer<ScenarioManager.Scenario> loaded,Consumer<String> log) {
        this.manager=manager; this.loaded=loaded; this.log=log;
        setPadding(new Insets(12)); setSpacing(8);
        aiMode.getItems().setAll("REPLAY","LIVE_AI"); aiMode.setValue("REPLAY"); simulated.setSelected(true);
        GridPane grid=new GridPane(); grid.setHgap(8); grid.setVgap(6);
        grid.add(new Label("案例名称"),0,0); grid.add(name,1,0);
        grid.add(new Label("AI 模式"),2,0); grid.add(aiMode,3,0);
        grid.add(new Label("演练速度 km/h"),0,1); grid.add(speed,1,1); grid.add(simulated,2,1,2,1);
        int row=0;
        for (var item:LABELS.entrySet()) {
            TextField field=new TextField(); field.setPrefWidth(360); fields.put(item.getKey(),field);
            int column=(row%2)*2, line=2+row/2;
            grid.add(new Label(item.getValue()),column,line);
            grid.add(field,column+1,line);
            row++;
        }
        cases.setPrefWidth(400); cases.setCellFactory(v->caseCell()); cases.setButtonCell(caseCell());
        status.setWrapText(true);
        getChildren().addAll(new Label("案例管理"),new HBox(8,cases,button("刷新",this::refresh),
                button("加载案例",this::load),button("删除案例",this::delete)),grid,
                new HBox(8,button("创建案例",this::save),button("检查缺失输入",this::check)),status);
        try { refresh(); }
        catch (Exception error) { status.setText("案例清单读取失败："+error.getMessage()); log.accept(status.getText()); }
    }
    private static ListCell<Path> caseCell() {
        return new ListCell<>() { @Override protected void updateItem(Path path,boolean empty) {
            super.updateItem(path,empty); setText(empty||path==null?"—":path.getFileName().toString());
        }};
    }
    @FunctionalInterface private interface Action { void run() throws Exception; }
    private Button button(String title,Action action) {
        Button button=new Button(title); button.setOnAction(e->{ try { action.run(); }
            catch (Exception error) { status.setText(title+"失败："+error.getMessage()); log.accept(status.getText()); } });
        return button;
    }
    public void refresh() throws Exception { cases.getItems().setAll(manager.list()); }
    private void save() throws Exception {
        var scenario=fromForm(); Path saved=manager.save(scenario); refresh(); cases.setValue(saved);
        loaded.accept(scenario); status.setText("已创建并加载案例："+saved); log.accept(status.getText());
    }
    private void load() throws Exception {
        Path selected=cases.getValue(); if (selected==null) throw new IllegalArgumentException("请选择案例");
        var scenario=manager.load(selected); fill(scenario); loaded.accept(scenario);
        status.setText("已加载案例："+scenario.name()); log.accept(status.getText());
    }
    private void delete() throws Exception {
        Path selected=cases.getValue(); if (selected==null) throw new IllegalArgumentException("请选择案例");
        manager.delete(selected); refresh(); cases.setValue(null);
        status.setText("已删除案例清单；源数据未删除："+selected); log.accept(status.getText());
    }
    private void check() {
        var missing=fromForm().missingForFullRun();
        status.setText(missing.isEmpty()?"案例字段完整；仍须核查源文件、MapGIS 图层、AI 服务和真实运行结果。":
                "缺少："+String.join("、",missing));
    }
    private String value(String key) { return fields.get(key).getText().trim(); }
    private ScenarioManager.Scenario fromForm() {
        return new ScenarioManager.Scenario(1,name.getText().trim(),simulated.isSelected(),aiMode.getValue(),
                value("preImage"),value("postImage"),value("predictionJson"),value("administrativeUrl"),
                value("populationUrl"),value("floodExtentUrl"),value("networkUrl"),value("sourceRoadsUrl"),
                value("resourceManifest"),value("roadStatusLedger"),value("startResourceId"),value("targetResourceId"),
                value("areaNameField"),value("resourceRiskField"),Double.parseDouble(speed.getText().trim()));
    }
    public void fill(ScenarioManager.Scenario s) {
        name.setText(s.name()); aiMode.setValue(s.aiMode()); simulated.setSelected(s.simulated());
        speed.setText(Double.toString(s.speedKph()));
        fields.get("preImage").setText(s.preImage()); fields.get("postImage").setText(s.postImage());
        fields.get("predictionJson").setText(s.predictionJson()); fields.get("administrativeUrl").setText(s.administrativeUrl());
        fields.get("populationUrl").setText(s.populationUrl()); fields.get("floodExtentUrl").setText(s.floodExtentUrl());
        fields.get("networkUrl").setText(s.networkUrl()); fields.get("sourceRoadsUrl").setText(s.sourceRoadsUrl());
        fields.get("resourceManifest").setText(s.resourceManifest()); fields.get("roadStatusLedger").setText(s.roadStatusLedger());
        fields.get("startResourceId").setText(s.startResourceId()); fields.get("targetResourceId").setText(s.targetResourceId());
        fields.get("areaNameField").setText(s.areaNameField()); fields.get("resourceRiskField").setText(s.resourceRiskField());
    }
}
