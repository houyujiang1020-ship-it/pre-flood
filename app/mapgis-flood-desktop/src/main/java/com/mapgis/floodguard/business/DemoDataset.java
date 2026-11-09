package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Audits the checked-in offline source bundle before any MapGIS-native conversion. */
public final class DemoDataset {
    private static final Map<String,String> SOURCES=Map.of(
            "pre_image","data/acceptance/gate5-v1/pre.tif",
            "post_image","data/acceptance/gate5-v1/post.tif",
            "buildings","data/demo/dispatch-spacenet8-endpoint-v2/buildings.geojson",
            "roads","data/demo/dispatch-spacenet8-endpoint-v2/roads.geojson",
            "population_grid","data/acceptance/gate5-v1/population-grid-100m.geojson",
            "administrative_source","data/acceptance/gate5-v1/community.geojson",
            "resource_source","data/demo/dispatch-spacenet8-endpoint-v2/resources.json");
    private final ObjectMapper json=new ObjectMapper();
    /** The configured repository takes precedence; otherwise locate it from the loaded plugin jar. */
    public static Path repositoryRoot() throws Exception {
        String configured=System.getProperty("floodguard.repo");
        if (configured!=null && !configured.isBlank()) {
            Path root=Path.of(configured);
            if (!root.isAbsolute()) throw new IllegalArgumentException("floodguard.repo 必须是项目根目录的绝对路径："+root);
            root=root.normalize();
            if (!Files.isDirectory(root.resolve("data")) || !Files.isDirectory(root.resolve("app/mapgis-flood-desktop")))
                throw new IllegalArgumentException("floodguard.repo 不是 FloodGuard 项目根目录："+root);
            return root;
        }
        Path location=Path.of(DemoDataset.class.getProtectionDomain().getCodeSource().getLocation().toURI())
                .toAbsolutePath().normalize();
        for (Path candidate=Files.isDirectory(location)?location:location.getParent(); candidate!=null; candidate=candidate.getParent()) {
            if (Files.isDirectory(candidate.resolve("data")) && Files.isDirectory(candidate.resolve("app/mapgis-flood-desktop")))
                return candidate;
        }
        throw new IllegalStateException("无法从插件位置定位 FloodGuard 项目根目录："+location+"；请设置绝对路径 -Dfloodguard.repo");
    }

    public Path auditProject() throws Exception {
        Path repository=repositoryRoot();
        return audit(repository,repository.resolve("outputs/demo-dataset-audit.json"));
    }

    public Path audit(Path repository,Path output) throws Exception {
        Objects.requireNonNull(repository); Objects.requireNonNull(output);
        repository=repository.toAbsolutePath().normalize();
        output=output.toAbsolutePath().normalize();
        Map<String,Object> items=new LinkedHashMap<>(); boolean allPresent=true;
        for (var entry:SOURCES.entrySet()) {
            Path file=repository.resolve(entry.getValue()).normalize();
            boolean present=Files.isRegularFile(file) && Files.size(file)>0;
            items.put(entry.getKey(),Map.of("path",file.toString(),"present",present));
            allPresent &= present;
        }
        Map<String,Object> report=new LinkedHashMap<>();
        report.put("schema_version",1); report.put("simulation_only",true);
        report.put("offline_source_files_present",allPresent); report.put("sources",items);
        report.put("full_demo_ready",false);
        report.put("missing_native_inputs",List.of("米制 MapGIS 行政区及资源距离风险字段",
                "明确标注来源的洪水面 MapGIS 图层","同一投影的对象级 flood_prediction.json",
                "已注册的 MapGIS 路网及资源库","与原始道路映射的封路证据"));
        report.put("reason","原始演练素材可离线读取，但不能替代 MapGIS 原生空间图层或完整演练验证");
        if (Files.isRegularFile(output)) {
            var previous=json.readTree(output.toFile());
            if (previous.has("p007_replay"))
                report.put("p007_replay",json.convertValue(previous.path("p007_replay"),Object.class));
        }
        Files.createDirectories(output.getParent());
        Files.writeString(output,json.writerWithDefaultPrettyPrinter().writeValueAsString(report),
                StandardCharsets.UTF_8,StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);
        if (!Files.isRegularFile(output)) throw new java.io.IOException("审计报告写入后不存在："+output);
        return output;
    }

    public static void main(String[] args) throws Exception {
        System.out.println(new DemoDataset().auditProject());
    }
}
