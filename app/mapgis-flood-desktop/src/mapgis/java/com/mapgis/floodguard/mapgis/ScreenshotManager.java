package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import javafx.application.Platform;
import javafx.scene.Node;
import javafx.scene.SnapshotParameters;
import javafx.scene.image.WritableImage;
import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.file.*;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;

/** Captures only a rendered JavaFX/MapGIS workspace after a completed stage. */
public final class ScreenshotManager {
    public enum Scene {
        HOME("01_系统首页.png"), DATA("01a_地图数据.png"), FLOOD("02_洪水检测结果.png"), DAMAGE("03_灾损分析.png"),
        RISK("04_风险评估.png"), CLOSURE("04a_道路封闭模拟.png"), ROUTE("05_路径规划.png"),
        RESOURCES("06_资源调度.png"), REPORT("07_综合报告.png");
        private final String filename;
        Scene(String filename) { this.filename=filename; }
        public String filename() { return filename; }
    }
    private final Path directory;
    private final boolean submissionNames;
    private final EnumMap<Scene,Path> captured=new EnumMap<>(Scene.class);
    private final EnumMap<Scene,Integer> capturedLayerCounts=new EnumMap<>(Scene.class);
    public ScreenshotManager(Path root,String runId) throws IOException {
        this(root,runId,false);
    }
    public ScreenshotManager(Path root,String runId,boolean submissionNames) throws IOException {
        if (runId==null || !runId.matches("[A-Za-z0-9_-]{1,80}")) throw new IllegalArgumentException("截图运行 ID 无效");
        directory=Files.createDirectories(root.resolve(runId)); this.submissionNames=submissionNames;
    }
    public Path directory() { return directory; }
    public Map<Scene,Path> captured() { return Collections.unmodifiableMap(captured); }
    public void verifySubmissionComplete() {
        for (Scene required:List.of(Scene.HOME,Scene.DATA,Scene.FLOOD,Scene.DAMAGE,Scene.RISK,Scene.CLOSURE,Scene.ROUTE,Scene.RESOURCES,Scene.REPORT))
            if (!captured.containsKey(required) || !Files.isRegularFile(captured.get(required)))
                throw new IllegalStateException("缺少真实演示截图："+filename(required));
    }
    private String filename(Scene scene) {
        if (!submissionNames) return scene.filename();
        return switch(scene) {
            case HOME -> "01_main.png"; case DATA -> "01a_map_data.png"; case FLOOD -> "02_flood.png";
            case DAMAGE -> "03_damage.png"; case RISK -> "04_risk.png";
            case CLOSURE -> "05_blockroad.png"; case ROUTE -> "06_route.png";
            case RESOURCES -> "07_resource.png"; case REPORT -> "08_report.png";
        };
    }
    public Path capture(Scene scene,Node workspace,int mapLayerCount) throws IOException {
        Objects.requireNonNull(scene); Objects.requireNonNull(workspace);
        if (!Platform.isFxApplicationThread() || workspace.getScene()==null)
            throw new IllegalStateException("只可在已显示的 JavaFX 工作台上采集真实运行截图");
        if (scene!=Scene.HOME && mapLayerCount<=0)
            throw new IllegalStateException("地图图层尚未加载，不能保存该阶段验收截图");
        WritableImage image=workspace.snapshot(new SnapshotParameters(),null);
        if (image==null || image.getWidth()<640 || image.getHeight()<480)
            throw new IllegalStateException("工作台尚未达到可验收的截图尺寸");
        BufferedImage pixels=new BufferedImage((int)image.getWidth(),(int)image.getHeight(),BufferedImage.TYPE_INT_ARGB);
        for (int y=0;y<pixels.getHeight();y++) for (int x=0;x<pixels.getWidth();x++)
            pixels.setRGB(x,y,image.getPixelReader().getArgb(x,y));
        Path output=directory.resolve(filename(scene));
        if (!ImageIO.write(pixels,"png",output.toFile())) throw new IOException("PNG 编码器不可用");
        captured.put(scene,output);
        capturedLayerCounts.put(scene,mapLayerCount);
        java.util.Map<String,Object> manifest=new LinkedHashMap<>();
        manifest.put("source","JavaFX Node.snapshot on displayed MapGIS workspace");
        manifest.put("visual_review_required",true);
        manifest.put("updated_at",Instant.now().toString());
        java.util.Map<String,Object> files=new LinkedHashMap<>();
        for (var item:captured.entrySet()) {
            Path path=item.getValue();
            String digest;
            try { digest=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path))); }
            catch (java.security.NoSuchAlgorithmException error) { throw new IOException("SHA-256 不可用",error); }
            java.util.Map<String,Object> detail=new LinkedHashMap<>();
            detail.put("filename",path.getFileName().toString()); detail.put("bytes",Files.size(path));
            detail.put("sha256",digest); detail.put("map_layer_count",capturedLayerCounts.get(item.getKey()));
            detail.put("function",item.getKey().name());
            detail.put("operation_step",item.getKey()==Scene.HOME?"打开 FloodGuard": "演练步骤完成后采集 "+item.getKey());
            detail.put("captured_at",Files.getLastModifiedTime(path).toInstant().toString());
            files.put(item.getKey().name(),detail);
        }
        manifest.put("captures",files);
        Files.writeString(directory.resolve("screenshots-manifest.json"),new ObjectMapper().writerWithDefaultPrettyPrinter()
                .writeValueAsString(manifest),StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);
        return output;
    }
}
