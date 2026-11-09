package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.JsonNode;
import com.mapgis.floodguard.report.SpatialResultManifest;
import java.nio.file.*;
import java.util.*;
import java.io.IOException;

/** Each result lives in a new directory; incomplete attempts never masquerade as completed manifests. */
public final class MapGisSpatialResultSet {
    public record Result(Path mask, Path overlay, Path manifest) {}
    public Result create(Path pre, Path post, JsonNode modelResult, Path directory) throws IOException {
        MapGisRasterSpatializer spatializer = new MapGisRasterSpatializer();
        spatializer.validatePair(pre, post);
        Map<String, Path> inputs = new LinkedHashMap<>();
        for (String key : SpatialResultManifest.CLASSES) inputs.put(key, input(modelResult.path("class_masks").path(key)));
        inputs.put("flood_mask", input(modelResult.path("mask_path")));
        inputs.put("overlay", input(modelResult.path("preview_path")));
        Files.createDirectory(directory);
        var reference = spatializer.inspect(pre);
        Map<String, SpatialResultManifest.RasterEvidence> outputs = new LinkedHashMap<>();
        for (var entry : inputs.entrySet()) {
            Path output = spatializer.spatialize(entry.getValue(), pre, directory.resolve(entry.getKey() + ".tif"));
            outputs.put(entry.getKey(), new SpatialResultManifest.RasterEvidence(output.toString(), spatializer.inspect(output)));
        }
        Path manifest = directory.resolve("spatial-result.json");
        new SpatialResultManifest().write(manifest, pre, post, reference, outputs, modelResult);
        return new Result(Path.of(outputs.get("flood_mask").path()), Path.of(outputs.get("overlay").path()), manifest);
    }
    private static Path input(JsonNode node) {
        if (!node.isTextual() || node.asText().isBlank()) throw new IllegalArgumentException("服务缺少分类结果路径");
        Path path = Path.of(node.asText()).toAbsolutePath();
        if (!Files.isRegularFile(path)) throw new IllegalArgumentException("分类结果文件不存在：" + path);
        return path;
    }
}
