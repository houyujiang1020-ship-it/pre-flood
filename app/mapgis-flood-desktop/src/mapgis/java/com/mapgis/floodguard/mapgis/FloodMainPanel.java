package com.mapgis.floodguard.mapgis;

import com.mapgis.floodguard.ai.AiServiceClient;
import com.mapgis.floodguard.ai.JobResponse;
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
    private final TextField pre = new TextField(System.getProperty("floodguard.pre", ""));
    private final TextField post = new TextField(System.getProperty("floodguard.post", ""));
    private final TextField output = new TextField(System.getProperty("floodguard.output", ""));
    private final TextField service = new TextField(System.getProperty("floodguard.ai.url", "http://127.0.0.1:8765/"));
    private final Button start = new Button("开始识别"), cancel = new Button("停止等待");
    private final Label status = new Label("请选择同一地理网格的灾前/灾后影像");
    private final ProgressBar progress = new ProgressBar(0);
    private final TextArea result = new TextArea();
    private final ImageView preview = new ImageView();
    private Task<JobResponse> task;
    private final IApplication application;
    private final Button loadMap = new Button("空间化并加载 MapGIS");
    private Path completedMask, completedReference;

    public FloodMainPanel(IApplication application) {
        this.application = application;
        setPadding(new Insets(18)); setSpacing(10);
        Label heading = new Label("洪涝智能识别与结果检查");
        heading.setStyle("-fx-font-size: 22px; -fx-font-weight: bold;");
        Label warning = new Label("当前默认模型为变化检测 fallback，不是已训练模型。像素数量不等于建筑栋数、道路条数或受淹面积。");
        warning.setWrapText(true);
        GridPane inputs = new GridPane(); inputs.setHgap(8); inputs.setVgap(8);
        addPath(inputs, 0, "灾前影像", pre, false);
        addPath(inputs, 1, "灾后影像", post, false);
        addPath(inputs, 2, "输出目录", output, true);
        inputs.addRow(3, new Label("AI 服务"), service);
        GridPane.setHgrow(service, Priority.ALWAYS);
        cancel.setDisable(true); start.setOnAction(event -> run());
        cancel.setOnAction(event -> { if (task != null) task.cancel(true); });
        loadMap.setDisable(true); loadMap.setOnAction(event -> loadSpatialResult());
        progress.setMaxWidth(Double.MAX_VALUE);
        result.setEditable(false); result.setWrapText(true); result.setPrefRowCount(8);
        preview.setFitWidth(270); preview.setFitHeight(270); preview.setPreserveRatio(true);
        HBox results = new HBox(12, result, preview); HBox.setHgrow(result, Priority.ALWAYS);
        Label mapStatus = new Label("空间化以本次灾前影像为参考，只接受同尺寸北向上网格。须先确认两期影像已在 MapGIS 配准；尚待授权后的现场验证。");
        mapStatus.setWrapText(true);
        getChildren().addAll(heading, warning, inputs, new HBox(10, start, cancel, loadMap), progress, status, results, mapStatus);
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

    private void run() {
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
        status.textProperty().bind(task.messageProperty()); progress.progressProperty().bind(task.progressProperty());
        task.setOnSucceeded(event -> {
            finish("识别完成；下方为原始像素统计，非 GIS 灾损结论");
            var data = task.getValue().result(); result.setText(data.toPrettyString());
            try {
                completedMask = Path.of(data.path("mask_path").asText()); completedReference = before;
                loadMap.setDisable(!Files.isRegularFile(completedMask));
                Path image = Path.of(data.path("preview_path").asText());
                if (Files.isRegularFile(image)) preview.setImage(new Image(image.toUri().toString(), true));
            } catch (RuntimeException error) { status.setText("结果已生成，预览失败：" + error.getMessage()); }
        });
        task.setOnFailed(event -> finish("识别失败：" + task.getException().getMessage()));
        task.setOnCancelled(event -> finish("已停止等待；服务端任务可能仍在执行，可通过任务 ID 查询"));
        Thread worker = new Thread(task, "floodguard-inference"); worker.setDaemon(true); worker.start();
    }

    private void finish(String message) {
        status.textProperty().unbind(); progress.progressProperty().unbind();
        start.setDisable(false); cancel.setDisable(true); status.setText(message);
    }
    private void loadSpatialResult() {
        try {
            Path outputTiff = completedMask.resolveSibling("flood-georeferenced-" + System.currentTimeMillis() + ".tif");
            Path georeferenced = new MapGisRasterSpatializer().spatialize(completedMask, completedReference, outputTiff);
            new MapGisResultLayerLoader().load(application, georeferenced, "受淹要素（模型结果，待核验）");
            status.setText("MapGIS 已加载空间化结果；仍须检查坐标、范围和实际位置");
        } catch (Exception | LinkageError error) {
            status.setText("空间化/加载失败：" + error.getMessage());
        }
    }
    @Override public void close() { if (task != null) task.cancel(true); }
}
