package com.mapgis.floodguard.mapgis;

import com.zondy.mapgis.pluginengine.IApplication;
import com.zondy.mapgis.pluginengine.plugin.ICommand;
import javafx.scene.Scene;
import javafx.stage.Stage;

/** Entry point registered through the installed MapGIS plugin manager. */
public final class FloodInferenceCommand implements ICommand {
    private IApplication application;
    private Stage stage;
    @Override public String getCaption() { return "洪涝智能识别"; }
    @Override public String getCategory() { return "洪涝应急"; }
    @Override public boolean isEnabled() { return application != null; }
    @Override public String getMessage() { return "打开洪涝识别工作面板"; }
    @Override public String getTooltip() { return "选择影像、调用 AI 并检查识别结果"; }
    @Override public void onCreate(IApplication app) { application = app; }
    @Override public void onClick() {
        if (stage == null) {
            stage = new Stage();
            stage.setTitle("MapGIS-FloodGuard · 洪涝智能识别");
            FloodMainPanel panel = new FloodMainPanel(application);
            stage.setScene(new Scene(panel, 820, 660));
            stage.setOnHidden(event -> { panel.close(); stage = null; });
        }
        stage.show(); stage.toFront();
    }
}
