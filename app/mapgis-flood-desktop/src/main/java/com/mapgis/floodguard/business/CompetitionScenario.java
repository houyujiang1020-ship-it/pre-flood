package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Validates formally prepared case manifests before passing them to the MapGIS host. */
public final class CompetitionScenario {
    private final ObjectMapper json=new ObjectMapper();
    public ScenarioManager.Scenario load(Path manifest) throws Exception {
        JsonNode root=json.readTree(manifest.toFile());
        if (!root.path("ready").asBoolean(false) || !Set.of("REAL","FORMALLY_PREPARED").contains(root.path("data_type").asText()))
            throw new IllegalArgumentException("真实案例尚未正式准备或标记为可运行");
        ScenarioManager.Scenario scenario=json.treeToValue(root.path("scenario"),ScenarioManager.Scenario.class);
        if (scenario.simulated() || !"REPLAY".equals(scenario.aiMode()) || !scenario.missingForFullRun().isEmpty())
            throw new IllegalArgumentException("真实案例字段缺失或仍标记为模拟");
        for (String url:List.of(scenario.administrativeUrl(),scenario.populationUrl(),scenario.floodExtentUrl(),
                scenario.networkUrl(),scenario.sourceRoadsUrl()))
            if (!url.startsWith("gdbp://")) throw new IllegalArgumentException("核心空间图层须为 MapGIS 原生 gdbp URL："+url);
        JsonNode sources=root.path("sources");
        if (!sources.isObject()) throw new IllegalArgumentException("真实案例缺少来源与 SHA-256 记录");
        Map<String,String> exact=Map.of("pre_image",scenario.preImage(),"post_image",scenario.postImage(),
                "prediction",scenario.predictionJson(),"resources",scenario.resourceManifest(),
                "road_status",scenario.roadStatusLedger());
        for (String key:List.of("pre_image","post_image","prediction","buildings","roads",
                "population","flood_extent","resources","road_status")) {
            JsonNode source=sources.path(key);
            String filename=source.path("path").asText("");
            if (filename.isBlank()) throw new IllegalArgumentException("来源路径缺失："+key);
            Path path=Path.of(filename);
            if (!path.isAbsolute()) path=manifest.toAbsolutePath().normalize().getParent().resolve(path).normalize();
            String expected=source.path("sha256").asText();
            if (!Files.isRegularFile(path) || !expected.matches("[0-9a-fA-F]{64}")
                    || source.path("provenance").asText().isBlank()
                    || source.path("license").asText().isBlank()
                    || source.path("source_date").asText().isBlank())
                throw new IllegalArgumentException("来源文件、SHA-256 或出处缺失："+key);
            if (exact.containsKey(key) && !path.toAbsolutePath().normalize().equals(Path.of(exact.get(key)).toAbsolutePath().normalize()))
                throw new IllegalArgumentException("案例字段与哈希来源路径不一致："+key);
            MessageDigest hash=MessageDigest.getInstance("SHA-256");
            try (var input=Files.newInputStream(path)) {
                byte[] block=new byte[1<<20]; for (int read;(read=input.read(block))!=-1;) hash.update(block,0,read);
            }
            String actual=HexFormat.of().formatHex(hash.digest());
            if (!actual.equalsIgnoreCase(expected)) throw new IllegalArgumentException("来源文件已变化："+key);
        }
        return scenario;
    }
}
