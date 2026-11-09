package com.mapgis.floodguard.mapgis;

import javafx.geometry.Insets;
import javafx.scene.control.Label;
import javafx.scene.layout.VBox;
import java.util.Locale;

/** Live status values from completed MapGIS analyses, never placeholder statistics. */
public final class DashboardPanel extends VBox {
    private final Label floodArea=new Label("未计算"), damagedBuildings=new Label("未计算"),
            affectedPopulation=new Label("未计算"), blockedRoads=new Label("未计算"),
            riskLevel=new Label("未计算"), availableResources=new Label("未加载"),
            routeDistance=new Label("未规划");
    public DashboardPanel() {
        setSpacing(8); setPadding(new Insets(12));
        getChildren().addAll(title("综合态势"),item("灾害区域面积",floodArea),item("受淹建筑",damagedBuildings),
                item("受影响人口",affectedPopulation),item("阻断道路",blockedRoads),
                item("风险等级",riskLevel),item("可用救援资源",availableResources),
                item("最佳路线距离",routeDistance));
    }
    private static Label title(String value) { Label label=new Label(value); label.setStyle("-fx-font-size:17px;-fx-font-weight:bold"); return label; }
    private static VBox item(String name,Label value) { value.setStyle("-fx-font-size:15px;-fx-font-weight:bold");
        return new VBox(2,new Label(name),value); }
    public void floodArea(double squareMetres) {
        if (!Double.isFinite(squareMetres) || squareMetres<0) throw new IllegalArgumentException("灾害面积无效");
        floodArea.setText(String.format(Locale.ROOT,"%.3f km²",squareMetres/1_000_000));
    }
    public void risk(FloodRiskAssessment.AreaResult result) {
        damagedBuildings.setText(Integer.toString(result.damagedBuildings()));
        affectedPopulation.setText(result.affectedPopulation()==null?"无法计算人口风险指标":
                String.format(Locale.ROOT,"%.0f",result.affectedPopulation()));
        blockedRoads.setText("VALID".equals(result.evidence().indicators().get("road").status())
                ? Integer.toString(result.blockedRoads()) : "状态待核查");
        riskLevel.setText(result.riskLevel()==null?"待补数据":result.riskLevel());
    }
    public void resources(int available) {
        if (available<0) throw new IllegalArgumentException("资源数无效"); availableResources.setText(Integer.toString(available));
    }
    public void route(EmergencyRoutePlanner.Result result) {
        routeDistance.setText(String.format(Locale.ROOT,"%.2f km",result.optimized().distanceMetres()/1000));
    }
}
