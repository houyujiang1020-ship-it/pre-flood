package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.util.*;

/** A formally prepared case must have its canonical inputs and MapGIS layer references. */
public final class OfficialDemoScenario {
    public ScenarioManager.Scenario load(Path manifest) throws Exception {
        Path source=manifest.toAbsolutePath().normalize();
        JsonNode root=new ObjectMapper().readTree(source.toFile());
        JsonNode files=root.path("sources");
        Map<String,String> names=Map.of("pre_image","pre.tif", "post_image","post.tif",
                "prediction","flood_prediction.json", "resources","resource-manifest.json",
                "road_status","road_status.json");
        for (String key:List.of("pre_image","post_image","prediction","buildings","roads",
                "population","flood_extent","resources","road_status")) {
            Path path=Path.of(files.path(key).path("path").asText("missing"));
            if (!path.isAbsolute()) path=source.getParent().resolve(path).normalize();
            String filename=path.getFileName().toString().toLowerCase(Locale.ROOT);
            if (names.containsKey(key) ? !filename.equals(names.get(key)) : !filename.startsWith(key+"."))
                throw new IllegalArgumentException("正式案例源文件名称不符合约定："+key+" → "+path);
        }
        return new CompetitionScenario().load(source);
    }
}
