package com.mapgis.floodguard.mapgis;

import com.mapgis.floodguard.ai.AiServiceClient;
import com.mapgis.floodguard.ai.JobResponse;
import com.mapgis.floodguard.business.AnalysisMode;
import com.zondy.mapgis.pluginengine.IApplication;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import javafx.concurrent.Task;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.*;
import javafx.stage.DirectoryChooser;
import javafx.stage.FileChooser;

/** Pixel statistics are never presented as GIS damage statistics. */
public final class FloodMainPanel extends VBox implements AutoCloseable {
    private java.util.function.Consumer<String> logSink = message -> {};
    private java.util.function.BiConsumer<Path,Path> spatialSink = (mask, patches) -> {};
    public void setLogSink(java.util.function.Consumer<String> sink) {
        logSink = sink;
        status.textProperty().addListener((o,a,b) -> sink.accept("模型/GIS：" + b));
        warning.textProperty().addListener((o,a,b) -> sink.accept("模型状态：" + b));
    }
    public void setSpatialSink(java.util.function.BiConsumer<Path,Path> sink) { spatialSink = sink; }
    private final TextField pre = new TextField(System.getProperty("floodguard.pre", ""));
    private final TextField post = new TextField(System.getProperty("floodguard.post", ""));
    private final TextField output = new TextField(System.getProperty("floodguard.output", ""));
    private final TextField service = new TextField(System.getProperty("floodguard.ai.url", "http://127.0.0.1:8765/"));
    private final Button start = new Button("开始识别"), cancel = new Button("停止等待");
    private final ComboBox<AnalysisMode> analysisMode = new ComboBox<>();
    private final Label modeBadge = new Label();
    private final Label status = new Label("请选择同一地理网格的灾前/灾后影像");
    private final ProgressBar progress = new ProgressBar(0);
    private final TextArea result = new TextArea();
    private final ImageView preview = new ImageView();
    private Task<JobResponse> task;
    private final IApplication application;
    private final Button loadMap = new Button("空间化并加载 MapGIS");
    private Path completedMask, completedReference;
    private Path completedPost;
    private com.fasterxml.jackson.databind.JsonNode completedResult;
    private final Button exportReport = new Button("导出识别记录");
    private final Label warning = new Label("尚未查询模型状态");
    private Task<com.mapgis.floodguard.ai.HealthResponse> healthTask;
    private final Button exportPatches = new Button("导出受淹斑块");
    private final Button assessEntities = new Button("建筑／道路核查");
    private final Button nativeCheck = new Button("原生栅格验收");
    private Path exportedPatches;
    private long inputsRevision;
    private Path completedPreview, spatialMask, spatialPreview, spatialManifest;
    private com.zondy.mapgis.map.RasterLayer beforeLayer, afterLayer, overlayLayer;
    private final Button showBefore = new Button("地图：灾前"), showAfter = new Button("地图：灾后"), showOverlay = new Button("地图：识别叠加");

    public FloodMainPanel(IApplication application) {
        this.application = application;
        setPadding(new Insets(18)); setSpacing(10);
        Label heading = new Label("洪涝智能识别与结果检查");
        heading.setStyle("-fx-font-size: 22px; -fx-font-weight: bold;");
        analysisMode.getItems().setAll(AnalysisMode.values());
        analysisMode.setValue(AnalysisMode.AI_PREDICTION);
        analysisMode.setConverter(new javafx.util.StringConverter<>() {
            @Override public String toString(AnalysisMode mode) { return mode == null ? "" : mode.display(); }
            @Override public AnalysisMode fromString(String value) { return AnalysisMode.valueOf(value); }
        });
        modeBadge.setStyle("-fx-font-weight:bold;-fx-padding:6;-fx-background-color:#ffe5b4;");
        analysisMode.valueProperty().addListener((o,a,b) -> applyAnalysisMode());
        warning.setWrapText(true);
        GridPane inputs = new GridPane(); inputs.setHgap(8); inputs.setVgap(8);
        addPath(inputs, 0, "灾前影像", pre, false);
        addPath(inputs, 1, "灾后影像", post, false);
        pre.textProperty().addListener((o,a,b) -> invalidateSpatialResult());
        post.textProperty().addListener((o,a,b) -> invalidateSpatialResult());
        addPath(inputs, 2, "输出目录", output, true);
        Button refresh = new Button("查询模型");
        refresh.setOnAction(event -> refreshModel());
        inputs.addRow(3, new Label("AI 服务"), service, refresh);
        service.textProperty().addListener((obs, oldText, newText) -> {
            if (healthTask != null) healthTask.cancel(true);
            warning.setText("服务地址已更改，请查询模型状态");
        });
        GridPane.setHgrow(service, Priority.ALWAYS);
        cancel.setDisable(true); start.setOnAction(event -> run());
        cancel.setOnAction(event -> { if (task != null) task.cancel(true); });
        loadMap.setDisable(true); loadMap.setOnAction(event -> loadSpatialResult());
        exportReport.setDisable(true); exportReport.setOnAction(event -> exportInferenceReport());
        exportPatches.setDisable(true); exportPatches.setOnAction(event -> exportPatches());
        assessEntities.setDisable(true); assessEntities.setOnAction(event -> openExposure());
        nativeCheck.setDisable(true); nativeCheck.setOnAction(event -> {
            Path evidence = spatialMask.resolveSibling("native-check-"+java.util.UUID.randomUUID());
            try {
                NativeRasterAcceptance.main(new String[]{completedReference.toString(),completedPost.toString(),spatialMask.toString(),evidence.toString()});
                status.setText("原生栅格及矢量化校验通过，证据："+evidence+"。不代表路网、渲染或模型精度通过。");
            } catch (Exception | LinkageError error) {
                error.printStackTrace(System.err); status.setText("原生验收失败："+error.getMessage()+"；证据目录："+evidence);
            }
        });
        progress.setMaxWidth(Double.MAX_VALUE);
        result.setEditable(false); result.setWrapText(true); result.setPrefRowCount(8);
        preview.setFitWidth(270); preview.setFitHeight(270); preview.setPreserveRatio(true);
        HBox results = new HBox(12, result, preview); HBox.setHgrow(result, Priority.ALWAYS);
        Label mapStatus = new Label("空间化需要带真实地理参考的同尺寸北向上配准影像；普通 PNG 仅供识别联调。地图加载后仍须核对坐标和范围，不能以加载成功代替精度验收。");
        mapStatus.setWrapText(true);
        for (Button button : new Button[]{showBefore, showAfter, showOverlay}) button.setDisable(true);
        showBefore.setOnAction(e -> switchMap(beforeLayer));
        showAfter.setOnAction(e -> switchMap(afterLayer));
        showOverlay.setOnAction(e -> switchMap(overlayLayer));
        Label legend = new Label("识别叠加：红色＝预测受淹建筑；橙色＝预测受淹道路。仅模型结果，不代表实际灾情。");
        Button buildExercise=new Button("创建演练路网");
        buildExercise.setOnAction(event -> {
            DirectoryChooser chooser=new DirectoryChooser(); chooser.setTitle("选择包含roads.geojson和manifest.json的演练数据目录");
            var selected=chooser.showDialog(getScene().getWindow()); if (selected==null) return;
            Path target=selected.toPath().resolve("mapgis-"+java.util.UUID.randomUUID());
            try {
                Path evidence=MapGisExerciseNetworkBuilder.build(selected.toPath(),target);
                String networkEvidence=java.nio.file.Files.readString(evidence);
                var buildResult=new com.fasterxml.jackson.databind.ObjectMapper().readTree(networkEvidence);
                status.setText("原生拓扑已生成；"+(buildResult.path("minute_defaults_verified").asBoolean()
                        ? "注册长度权准备通过；资源绑定及阻断验收状态见下方。"
                        : "注册长度权准备未通过，详情见下方；调度尚未就绪。"));
                Path preparation=target.resolve("dispatch-preparation.json");
                result.setText(networkEvidence+(java.nio.file.Files.isRegularFile(preparation)
                        ? "\n\n调度准备证据：\n"+java.nio.file.Files.readString(preparation) : ""));
                Path exerciseEvidence=target.resolve("exercise-dispatch.json");
                if (java.nio.file.Files.isRegularFile(exerciseEvidence)) {
                    result.appendText("\n\n资源绑定与封路演练：\n"+java.nio.file.Files.readString(exerciseEvidence));
                    status.setText("拓扑已生成；"+(buildResult.path("exercise_routes_verified").asBoolean()
                            ? "演练绑定及封路路径检查通过；正式业务调度未验收。"
                            : "演练绑定/路径检查未通过，详情见结果框；不是建网失败。"));
                }
            } catch (Exception | LinkageError error) {
                error.printStackTrace(System.err); status.setText("建网未完成："+error.getMessage()+"；证据："+target);
                try { result.setText(java.nio.file.Files.readString(target.resolve("network-build.json"))); }
                catch (java.io.IOException unavailable) { result.setText("建网失败："+error+"\n证据文件未生成："+target+"\n"+unavailable); }
            }
        });
        legend.setWrapText(true);
        getChildren().addAll(heading, new HBox(10, new Label("分析模式"), analysisMode, modeBadge), warning, inputs, new HBox(10, start, cancel, loadMap, exportReport),
                new FlowPane(10, 8, showBefore, showAfter, showOverlay, exportPatches, assessEntities, nativeCheck, buildExercise), progress, status, results, legend, mapStatus);
        applyAnalysisMode();
        refreshModel();
        if (Boolean.getBoolean("floodguard.auto.acceptance")) {
            javafx.application.Platform.runLater(this::run);
        }
    }

    private void refreshModel() {
        if (analysisMode.getValue() == AnalysisMode.GROUND_TRUTH_VALIDATION) {
            warning.setText("GT VALIDATION：不调用 AI 服务；只接受固定数据集及真实 MapGIS 验收证据。");
            return;
        }
        if (healthTask != null) healthTask.cancel(true);
        String address = service.getText().trim();
        warning.setText("正在查询实际模型状态…");
        Task<com.mapgis.floodguard.ai.HealthResponse> query = new Task<>() {
            @Override protected com.mapgis.floodguard.ai.HealthResponse call() throws Exception {
                return new AiServiceClient(URI.create(address)).health();
            }
        };
        healthTask = query;
        query.setOnSucceeded(e -> { if (healthTask == query) warning.setText(query.getValue().displaySummary()); });
        query.setOnFailed(e -> { if (healthTask == query) warning.setText("无法确认模型状态：" + query.getException().getMessage()); });
        Thread worker = new Thread(query, "floodguard-model-info"); worker.setDaemon(true); worker.start();
    }

    private void addPath(GridPane grid, int row, String label, TextField field, boolean directory) {
        Button browse = new Button("选择…");
        browse.setOnAction(event -> {
            java.io.File selected;
            if (directory) {
                DirectoryChooser chooser = new DirectoryChooser(); chooser.setTitle(label);
                selected = chooser.showDialog(getScene().getWindow());
            } else {
                FileChooser chooser = new FileChooser(); chooser.setTitle(label);
                chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("影像", "*.tif", "*.tiff", "*.png", "*.jpg"));
                selected = chooser.showOpenDialog(getScene().getWindow());
            }
            if (selected != null) field.setText(selected.getAbsolutePath());
        });
        grid.addRow(row, new Label(label), field, browse); GridPane.setHgrow(field, Priority.ALWAYS);
    }

    public void setInputPaths(String before, String after) {
        pre.setText(before == null ? "" : before);
        post.setText(after == null ? "" : after);
    }

    private void invalidateSpatialResult() {
        inputsRevision++;
        if (task != null && task.isRunning()) task.cancel(true);
        if (status.textProperty().isBound()) status.textProperty().unbind();
        if (progress.progressProperty().isBound()) progress.progressProperty().unbind();
        if (beforeLayer!=null || afterLayer!=null || overlayLayer!=null) {
            try {
                var view=(com.zondy.mapgis.pluginengine.plugin.IMapContentsView)application.getActiveContentsView();
                var control=view.getMapControl();
                for (var layer:new com.zondy.mapgis.map.RasterLayer[]{beforeLayer,afterLayer,overlayLayer})
                    if (layer!=null && layer.getHandle()!=0) control.getMap().remove(layer);
                control.refreshWnd();
            } catch (RuntimeException | LinkageError error) {
                logSink.accept("切换影像时清理旧地图图层失败："+error);
            }
        }
        completedMask=null; completedReference=null; completedPost=null; completedResult=null;
        spatialMask=null; spatialPreview=null; spatialManifest=null; exportedPatches=null;
        beforeLayer=null; afterLayer=null; overlayLayer=null;
        loadMap.setDisable(true); exportPatches.setDisable(true); assessEntities.setDisable(true);
        nativeCheck.setDisable(true);
        for (Button button:new Button[]{showBefore,showAfter,showOverlay}) button.setDisable(true);
        spatialSink.accept(null,null);
        status.setText("影像输入已更改；旧空间结果已失效，请重新识别并空间化");
    }

    private void run() {
        if (analysisMode.getValue() != AnalysisMode.AI_PREDICTION) {
            status.setText("GT VALIDATION 禁止启动 AI 识别。请使用固定 Gate 5 数据和真值验收流程。");
            return;
        }
        refreshModel();
        final Path before, after, destination;
        final URI endpoint;
        try {
            if (pre.getText().isBlank() || post.getText().isBlank() || output.getText().isBlank())
                throw new IllegalArgumentException("请填写两幅影像及输出目录");
            before = Path.of(pre.getText()); after = Path.of(post.getText()); destination = Path.of(output.getText());
            if (!Files.isRegularFile(before) || !Files.isRegularFile(after)) throw new IllegalArgumentException("影像文件不存在");
            endpoint = URI.create(service.getText().trim());
            if (!("http".equals(endpoint.getScheme()) || "https".equals(endpoint.getScheme())) || endpoint.getHost() == null)
                throw new IllegalArgumentException("AI 地址必须为完整 HTTP/HTTPS 地址");
        } catch (RuntimeException error) { status.setText(error.getMessage()); return; }
        invalidateSpatialResult();
        final long runRevision=inputsRevision;
        task = new Task<>() {
            @Override protected JobResponse call() throws Exception {
                AiServiceClient client = new AiServiceClient(endpoint);
                updateMessage("检查 AI 服务…");
                if (!client.health().model_loaded()) throw new IllegalStateException("AI 模型未加载");
                JobResponse job = client.submit(before, after, destination);
                Instant deadline = Instant.now().plus(Duration.ofMinutes(10));
                while (!isCancelled()) {
                    updateProgress(job.progress(), 100);
                    updateMessage("任务 " + job.job_id() + " · " + job.status() + " · " + job.progress() + "%");
                    if ("completed".equals(job.status())) {
                        if (job.result() == null || !job.result().isObject()) throw new IllegalStateException("服务未返回有效结果");
                        return job;
                    }
                    if ("failed".equals(job.status())) throw new IllegalStateException(job.error());
                    if (Instant.now().isAfter(deadline)) throw new IllegalStateException("等待超时，可使用任务 ID 查询服务结果");
                    Thread.sleep(500); job = client.job(job.job_id());
                }
                return null;
            }
        };
        result.clear(); preview.setImage(null); start.setDisable(true); cancel.setDisable(false); loadMap.setDisable(true);
        exportReport.setDisable(true);
        exportPatches.setDisable(true);
        assessEntities.setDisable(true); exportedPatches = null;
        nativeCheck.setDisable(true);
        status.textProperty().bind(task.messageProperty()); progress.progressProperty().bind(task.progressProperty());
        task.setOnSucceeded(event -> {
            if (runRevision!=inputsRevision) return;
            finish("识别完成；下方为原始像素统计，非 GIS 灾损结论");
            var data = task.getValue().result(); result.setText(data.toPrettyString());
            completedResult = data.deepCopy(); completedPost = after;
            spatialMask = null; spatialPreview = null; spatialManifest = null;
            for (Button button : new Button[]{showBefore, showAfter, showOverlay}) button.setDisable(true);
            try {
                completedMask = Path.of(data.path("mask_path").asText()); completedReference = before;
                exportReport.setDisable(false);
                String referenceName = before.getFileName().toString().toLowerCase(java.util.Locale.ROOT);
                loadMap.setDisable(!Files.isRegularFile(completedMask)
                        || !(referenceName.endsWith(".tif") || referenceName.endsWith(".tiff")));
                Path image = Path.of(data.path("preview_path").asText());
                completedPreview = image;
                if (Files.isRegularFile(image)) preview.setImage(new Image(image.toUri().toString(), true));
                if (Boolean.getBoolean("floodguard.auto.acceptance") && !loadMap.isDisabled()) {
                    javafx.application.Platform.runLater(this::loadSpatialResult);
                }
            } catch (RuntimeException error) { status.setText("结果已生成，预览失败：" + error.getMessage()); }
        });
        task.setOnFailed(event -> finish("识别失败：" + task.getException().getMessage()));
        task.setOnCancelled(event -> finish("已停止等待；服务端任务可能仍在执行，可通过任务 ID 查询"));
        Thread worker = new Thread(task, "floodguard-inference"); worker.setDaemon(true); worker.start();
    }

    private void applyAnalysisMode() {
        AnalysisMode mode = analysisMode.getValue();
        boolean gt = mode == AnalysisMode.GROUND_TRUTH_VALIDATION;
        modeBadge.setText(gt ? "GT VALIDATION · 官方真值" : "AI PREDICTION · 模型输出");
        modeBadge.setStyle("-fx-font-weight:bold;-fx-padding:6;-fx-background-color:" + (gt ? "#b7e4c7" : "#ffe5b4") + ";");
        start.setDisable(gt || (task != null && task.isRunning()));
        service.setDisable(gt);
        if (gt) {
            if (healthTask != null) healthTask.cancel(true);
            warning.setText("GT VALIDATION：不调用 AI 服务；continuous flood area 与 blocked road count 保持 N/A。");
            status.setText("GT VALIDATION 已选择。加载固定 Gate 5 数据后执行 MapGIS 现场验收。");
        } else {
            warning.setText("AI PREDICTION：模型结果不得冒充真值灾损。");
        }
    }

    private void finish(String message) {
        status.textProperty().unbind(); progress.progressProperty().unbind();
        start.setDisable(analysisMode.getValue() != AnalysisMode.AI_PREDICTION); cancel.setDisable(true); status.setText(message);
    }
    private void loadSpatialResult() {
        loadMap.setDisable(true);
        try {
            if (spatialManifest == null) {
                var spatial = new MapGisSpatialResultSet().create(completedReference, completedPost, completedResult,
                        completedMask.resolveSibling("mapgis-" + java.util.UUID.randomUUID()));
                spatialMask = spatial.mask(); spatialPreview = spatial.overlay(); spatialManifest = spatial.manifest();
            }
            MapGisResultLayerLoader loader = new MapGisResultLayerLoader();
            beforeLayer = loader.load(application, completedReference, "灾前影像");
            afterLayer = loader.load(application, completedPost, "灾后影像");
            overlayLayer = loader.load(application, spatialPreview, "识别叠加（红：建筑；橙：道路；待核验）");
            loader.showOnly(application, overlayLayer, beforeLayer, afterLayer, overlayLayer);
            for (Button button : new Button[]{showBefore, showAfter, showOverlay}) button.setDisable(false);
            exportPatches.setDisable(false);
            nativeCheck.setDisable(false);
            assessEntities.setDisable(false);
            spatialSink.accept(spatialMask, null);
            status.setText("已加载对照图层；四类空间化结果与验证记录已保存：" + spatialManifest
                    + "。请最小化面板检查实际显示。");
        } catch (Exception | LinkageError error) {
            error.printStackTrace(System.err);
            status.setText("空间化/加载失败：" + error.getMessage());
        } finally { loadMap.setDisable(false); }
    }
    private void switchMap(com.zondy.mapgis.map.RasterLayer selected) {
        try {
            new MapGisResultLayerLoader().showOnly(application, selected, beforeLayer, afterLayer, overlayLayer);
            status.setText("已切换地图视图，请最小化面板查看；结果仍待核验");
        } catch (Exception | LinkageError error) { status.setText("地图切换失败：" + error.getMessage()); }
    }
    private void exportInferenceReport() {
        FileChooser chooser = new FileChooser(); chooser.setTitle("保存模型识别记录（非 GIS 灾情报告）");
        chooser.setInitialFileName("模型识别记录-" + System.currentTimeMillis() + ".html");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("HTML", "*.html"));
        java.io.File file = chooser.showSaveDialog(getScene().getWindow());
        if (file == null) return;
        try {
            String html = new com.mapgis.floodguard.report.HtmlInferenceReport().render("洪涝识别", completedReference, completedPost, completedResult);
            Files.writeString(file.toPath(), html, java.nio.charset.StandardCharsets.UTF_8, java.nio.file.StandardOpenOption.CREATE_NEW);
            status.setText("已导出实际模型结果：" + file.getAbsolutePath());
        } catch (Exception error) { status.setText("导出失败（不会覆盖已有文件）：" + error.getMessage()); }
    }
    private void exportPatches() {
        exportPatches.setDisable(true);
        try {
            Path file = spatialMask.resolveSibling("predicted-patches-" + java.util.UUID.randomUUID() + ".geojson");
            new MapGisMaskVectorizer().export(spatialMask, file);
            exportedPatches = file;
            spatialSink.accept(spatialMask, exportedPatches);
            status.setText("MapGIS矢量斑块已导出（不是建筑栋数或完整洪水范围）：" + file);
        } catch (Exception | LinkageError error) {
            error.printStackTrace(System.err);
            status.setText("矢量化失败：" + error.getMessage());
        } finally { exportPatches.setDisable(false); }
    }
    private void openExposure() {
        try {
            if (exportedPatches == null) {
                Path file = spatialMask.resolveSibling("predicted-patches-" + java.util.UUID.randomUUID() + ".geojson");
                new MapGisMaskVectorizer().export(spatialMask,file);
                exportedPatches = file;
            }
            javafx.stage.Stage window = new javafx.stage.Stage();
            window.setTitle("MapGIS · 建筑与道路实体核查");
            window.initOwner(getScene().getWindow());
            ExposurePanel panel=new ExposurePanel(application,spatialMask,exportedPatches,() -> this.spatialMask);
            panel.setLogSink(logSink);
            window.setScene(new javafx.scene.Scene(panel,860,640));
            window.show();
        } catch (Exception | LinkageError error) {
            error.printStackTrace(System.err); status.setText("打开实体核查失败："+error.getMessage());
        }
    }
    @Override public void close() {
        if (task != null) task.cancel(true);
        if (healthTask != null) healthTask.cancel(true);
    }
}
