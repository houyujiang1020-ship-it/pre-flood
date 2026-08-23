package com.mapgis.floodguard.mapgis;

import com.mapgis.floodguard.ai.AiServiceClient;
import com.mapgis.floodguard.ai.JobResponse;
import com.zondy.mapgis.pluginengine.IApplication;
import com.zondy.mapgis.pluginengine.plugin.ICommand;
import java.net.URI;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.CompletableFuture;
import javafx.application.Platform;
import javafx.scene.control.Alert;

/** MapGIS command driven by floodguard.pre/post/output system properties. */
public final class FloodInferenceCommand implements ICommand {
    private IApplication application;

    @Override public String getCaption() { return "洪涝智能识别"; }
    @Override public String getCategory() { return "洪涝应急"; }
    @Override public boolean isEnabled() { return application != null; }
    @Override public String getMessage() { return "调用 AI 服务并加载洪涝结果"; }
    @Override public String getTooltip() { return "洪涝智能识别"; }

    @Override
    public void onClick() {
        String pre = System.getProperty("floodguard.pre");
        String post = System.getProperty("floodguard.post");
        String output = System.getProperty("floodguard.output");
        if (pre == null || post == null || output == null) {
            showError("请设置 floodguard.pre、floodguard.post 和 floodguard.output 启动参数");
            return;
        }
        URI service = URI.create(System.getProperty("floodguard.ai.url", "http://127.0.0.1:8765/"));
        CompletableFuture.supplyAsync(() -> infer(service, Path.of(pre), Path.of(post), Path.of(output)))
                .thenAccept(mask -> Platform.runLater(() -> loadResult(mask)))
                .exceptionally(error -> { Platform.runLater(() -> showError(rootMessage(error))); return null; });
    }

    private Path infer(URI service, Path pre, Path post, Path output) {
        try {
            AiServiceClient client = new AiServiceClient(service);
            JobResponse job = client.submit(pre, post, output);
            Instant deadline = Instant.now().plus(Duration.ofMinutes(10));
            while (!"completed".equals(job.status())) {
                if ("failed".equals(job.status())) throw new IllegalStateException(job.error());
                if (Instant.now().isAfter(deadline)) throw new IllegalStateException("AI 推理等待超时");
                Thread.sleep(500);
                job = client.job(job.job_id());
            }
            return Path.of(job.result().path("mask_path").asText());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("AI 推理被中断", e);
        } catch (Exception e) {
            throw new IllegalStateException("AI 推理失败: " + e.getMessage(), e);
        }
    }

    private void loadResult(Path mask) {
        try { new MapGisResultLayerLoader().load(application, mask, "洪涝范围"); }
        catch (RuntimeException e) { showError(e.getMessage()); }
    }

    private void showError(String message) {
        Alert alert = new Alert(Alert.AlertType.ERROR, message);
        alert.setHeaderText("MapGIS-FloodGuard");
        alert.show();
    }

    private static String rootMessage(Throwable error) {
        Throwable current = error;
        while (current.getCause() != null) current = current.getCause();
        return current.getMessage();
    }

    @Override public void onCreate(IApplication app) { this.application = app; }
}
