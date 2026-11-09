package com.zondy.mapgis.floodguard.plugin;

import com.mapgis.floodguard.mapgis.FloodGuardMainWindow;
import com.mapgis.floodguard.business.MapGISEnvironmentChecker;
import com.mapgis.floodguard.business.FinalEnvironmentCheck;
import com.mapgis.floodguard.business.StartupLog;
import com.zondy.mapgis.pluginengine.IApplication;
import com.zondy.mapgis.pluginengine.plugin.ICommand;
import javafx.scene.Scene;
import javafx.scene.control.Alert;
import javafx.application.Platform;
import javafx.stage.Stage;
import java.nio.file.Path;

/** Entry point registered through the installed MapGIS plugin manager. */
public final class FloodInferenceCommand implements ICommand {
    private IApplication application;
    private Stage stage;
    @Override public String getCaption() { return "洪涝应急决策平台"; }
    @Override public String getCategory() { return "洪涝应急"; }
    // MapGIS snapshots this value BEFORE onCreate; opening this panel needs no active map.
    @Override public boolean isEnabled() { return true; }
    @Override public String getMessage() { return "打开 FloodGuard GIS 工作台"; }
    @Override public String getTooltip() { return "MapGIS 地图、洪水检测、灾损分析与应急调度"; }
    @Override public void onCreate(IApplication app) {
        application = app;
        if (Boolean.getBoolean("floodguard.auto.open")) {
            Platform.runLater(this::onClick);
        }
    }
    @Override public void onClick() {
        if (application == null) {
            new Alert(Alert.AlertType.ERROR, "MapGIS 命令尚未初始化，请重启项目桌面并查看日志。").show();
            return;
        }
        Path program=Path.of(System.getProperty("floodguard.mapgis.home","C:/Program Files/MapGIS 10/Program"));
        Path report=Path.of(System.getProperty("floodguard.environment.report","outputs/environment_check.json"));
        Path finalReport=Path.of(System.getProperty("floodguard.final.environment.report","submission/final_environment_report.json"));
        StartupLog startup=new StartupLog(Path.of(System.getProperty("floodguard.startup.log","startup_log.json")));
        MapGISEnvironmentChecker checker=new MapGISEnvironmentChecker();
        try {
        startup.checkpoint("plugin","READY");
        var preflight=checker.check(program,report,true,false,null);
        startup.checkpoint("sdk",preflight.canCreateMap()?"READY":"FAILED_PREFLIGHT");
        new FinalEnvironmentCheck().generate(report,finalReport);
        if (!preflight.canCreateMap()) {
            new Alert(Alert.AlertType.ERROR,"MapGIS 环境不完整："+String.join("、",preflight.missing())+
                    "\n"+String.join("\n",preflight.recommendations())+"\n诊断："+report).show();
            return;
        }
        if (stage == null) {
            FloodGuardMainWindow panel = new FloodGuardMainWindow(application);
            startup.checkpoint("map","MAPCONTROL_CREATED");
            checker.check(program,report,true,true,null);
            new FinalEnvironmentCheck().generate(report,finalReport);
            Stage candidate = new Stage();
            candidate.setTitle("MapGIS-FloodGuard · 洪涝灾害智能分析与应急决策平台");
            candidate.setScene(new Scene(panel, 1440, 900));
            candidate.setOnHidden(event -> { panel.close(); stage = null; });
            stage = candidate;
        }
        stage.show(); stage.toFront();
        startup.checkpoint("map","WINDOW_SHOWN");
        } catch (RuntimeException | LinkageError error) {
            error.printStackTrace(System.err);
            try { checker.check(program,report,true,false,error);
                new FinalEnvironmentCheck().generate(report,finalReport); }
            catch (Exception diagnosticError) { diagnosticError.printStackTrace(System.err); }
            if (stage != null) stage.hide();
            stage = null;
            try { startup.failure(error); } catch (Exception ignored) { error.addSuppressed(ignored); }
            new Alert(Alert.AlertType.ERROR, "MapGIS 初始化失败：" + error +
                    "\n请检查 MapGIS 运行环境和授权状态。诊断："+report).show();
        } catch (Exception error) {
            error.printStackTrace(System.err);
            try { startup.failure(error); } catch (Exception ignored) { error.addSuppressed(ignored); }
            new Alert(Alert.AlertType.ERROR,"环境诊断失败："+error+"\n请检查输出目录权限。诊断："+report).show();
        }
    }
}
