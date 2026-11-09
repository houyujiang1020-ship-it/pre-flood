package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Owns only case manifests; deleting a case never deletes its source datasets. */
public final class ScenarioManager {
    public record Scenario(int schemaVersion,String name,boolean simulated,String aiMode,
                           String preImage,String postImage,String predictionJson,
                           String administrativeUrl,String populationUrl,String floodExtentUrl,
                           String networkUrl,String sourceRoadsUrl,String resourceManifest,
                           String roadStatusLedger,String startResourceId,String targetResourceId,
                           String areaNameField,String resourceRiskField,double speedKph) {
        public Scenario {
            if (schemaVersion!=1 || name==null || name.isBlank() || name.length()>100
                    || !Set.of("LIVE_AI","REPLAY").contains(aiMode)
                    || !Double.isFinite(speedKph) || speedKph<=0 || speedKph>130)
                throw new IllegalArgumentException("案例名称、AI 模式和演练速度无效");
            for (String value:List.of(preImage,postImage,predictionJson,administrativeUrl,populationUrl,
                    floodExtentUrl,networkUrl,sourceRoadsUrl,resourceManifest,roadStatusLedger,
                    startResourceId,targetResourceId,areaNameField,resourceRiskField))
                if (value==null || value.length()>4096) throw new IllegalArgumentException("案例字段缺失或过长");
        }
        public List<String> missingForFullRun() {
            Map<String,String> required=new LinkedHashMap<>();
            required.put("灾前影像",preImage); required.put("灾后影像",postImage);
            required.put("灾损预测 JSON",predictionJson); required.put("行政区域 MapGIS URL",administrativeUrl);
            required.put("人口格网 MapGIS URL",populationUrl); required.put("真实洪水面 MapGIS URL",floodExtentUrl);
            required.put("路网 MapGIS URL",networkUrl); required.put("原始道路 MapGIS URL",sourceRoadsUrl);
            required.put("资源清单",resourceManifest); required.put("道路状态核查单",roadStatusLedger);
            required.put("车辆编号",startResourceId); required.put("目标编号",targetResourceId);
            required.put("区域名称字段",areaNameField); required.put("资源距离风险字段",resourceRiskField);
            return required.entrySet().stream().filter(e->e.getValue().isBlank()).map(Map.Entry::getKey).toList();
        }
    }
    private final Path directory;
    private final ObjectMapper json=new ObjectMapper();
    public ScenarioManager(Path directory) throws IOException {
        this.directory=Files.createDirectories(directory).toAbsolutePath().normalize();
    }
    public Path directory() { return directory; }
    public Path save(Scenario scenario) throws IOException {
        Objects.requireNonNull(scenario);
        Path file=directory.resolve("scenario-"+UUID.randomUUID()+".json");
        Path temp=Files.createTempFile(directory,"scenario-",".tmp");
        try {
            Files.writeString(temp,json.writerWithDefaultPrettyPrinter().writeValueAsString(scenario));
            try { Files.move(temp,file,StandardCopyOption.ATOMIC_MOVE); }
            catch (AtomicMoveNotSupportedException unavailable) { Files.move(temp,file); }
            return file;
        } finally { Files.deleteIfExists(temp); }
    }
    public Scenario load(Path file) throws IOException {
        Path target=managed(file);
        if (!Files.isRegularFile(target) || Files.size(target)>100_000) throw new IllegalArgumentException("案例清单不存在或过大");
        return json.readValue(target.toFile(),Scenario.class);
    }
    public List<Path> list() throws IOException {
        try (var files=Files.list(directory)) {
            return files.filter(p->p.getFileName().toString().startsWith("scenario-")
                    && p.getFileName().toString().endsWith(".json") && Files.isRegularFile(p))
                    .sorted().toList();
        }
    }
    public void delete(Path file) throws IOException { Files.delete(managed(file)); }
    private Path managed(Path file) {
        Path target=Objects.requireNonNull(file).toAbsolutePath().normalize();
        if (!target.getParent().equals(directory) || !target.getFileName().toString().startsWith("scenario-")
                || !target.getFileName().toString().endsWith(".json"))
            throw new IllegalArgumentException("只能操作案例目录内的案例 JSON");
        return target;
    }
}
