package com.mapgis.floodguard.report;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.mapgis.floodguard.business.RasterGrid;
import java.io.IOException;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/** File-level evidence only: never infer rendering, feature counts or model accuracy. */
public final class SpatialResultManifest {
    public static final List<String> CLASSES = List.of("non_flooded_building", "flooded_building", "non_flooded_road", "flooded_road");
    public record RasterEvidence(String path, RasterGrid grid) {}
    public void write(Path target, Path pre, Path post, RasterGrid reference,
                      Map<String, RasterEvidence> outputs, JsonNode modelResult) throws IOException {
        if (!outputs.keySet().containsAll(CLASSES) || !outputs.containsKey("flood_mask") || !outputs.containsKey("overlay"))
            throw new IllegalArgumentException("Incomplete spatial result set");
        for (RasterEvidence raster : outputs.values()) {
            reference.requireSame(raster.grid());
            if (!Files.isRegularFile(Path.of(raster.path()))) throw new IllegalArgumentException("Spatial output missing");
        }
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("schema_version", 1);
        report.put("created_at", Instant.now().toString());
        report.put("pre_image", pre.toAbsolutePath().toString());
        report.put("post_image", post.toAbsolutePath().toString());
        report.put("engine", "MapGIS Objects Java");
        report.put("outputs", outputs);
        report.put("model_result", modelResult);
        report.put("grid_verified", true);
        report.put("map_rendering_verified", false);
        report.put("damage_analysis_completed", false);
        report.put("production_ready", false);
        report.put("warning", "Pixel class masks, not building instances/road segments or a full flood extent. Rendering and GIS damage analysis remain unverified.");
        Files.writeString(target, new ObjectMapper().writerWithDefaultPrettyPrinter().writeValueAsString(report),
                java.nio.charset.StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
    }
}
