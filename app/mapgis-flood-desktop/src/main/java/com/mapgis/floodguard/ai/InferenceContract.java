package com.mapgis.floodguard.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;

/** Verifies service evidence before any native GIS bridge is attempted. */
public final class InferenceContract {
    public static final List<String> CLASSES = List.of("non_flooded_building", "flooded_building",
            "non_flooded_road", "flooded_road");
    private static final ObjectMapper JSON = new ObjectMapper();
    private InferenceContract() {}

    public static JsonNode verify(JobResponse job) throws Exception {
        if (job == null || !"completed".equals(job.status()) || job.result() == null)
            throw new IllegalArgumentException("AI job did not complete");
        JsonNode result = job.result();
        Path file = Path.of(result.path("contract_path").asText(""));
        if (!Files.isRegularFile(file) || Files.size(file) > 1_000_000)
            throw new IllegalArgumentException("Missing or oversized inference contract");
        requireHash(file, result.path("contract_sha256").asText());
        JsonNode root = JSON.readTree(file.toFile());
        if (root.path("schema_version").asInt() != 2 || !job.job_id().equals(root.path("task_id").asText()))
            throw new IllegalArgumentException("Inference contract version/task mismatch");
        String mode = root.path("execution_mode").asText();
        if (!List.of("FALLBACK", "SMOKE", "LIVE_E4").contains(mode))
            throw new IllegalArgumentException("Unknown inference mode");
        if (root.path("class_order").size() != CLASSES.size()) throw new IllegalArgumentException("Class order missing");
        for (int i = 0; i < CLASSES.size(); i++)
            if (!CLASSES.get(i).equals(root.path("class_order").get(i).asText()))
                throw new IllegalArgumentException("Class order mismatch");
        JsonNode pre = root.path("input_metadata").path("pre"), post = root.path("input_metadata").path("post");
        int width = pre.path("width").asInt(), height = pre.path("height").asInt();
        if (width <= 0 || height <= 0 || width != post.path("width").asInt() || height != post.path("height").asInt())
            throw new IllegalArgumentException("Input image dimensions differ");
        for (JsonNode source : List.of(pre, post)) requireHash(Path.of(source.path("path").asText("")), source.path("sha256").asText());
        for (String name : CLASSES) {
            JsonNode mask = root.path("prediction_outputs").path(name);
            if (mask.path("width").asInt() != width || mask.path("height").asInt() != height)
                throw new IllegalArgumentException("Mask dimensions differ: " + name);
            requireHash(Path.of(mask.path("path").asText("")), mask.path("sha256").asText());
        }
        JsonNode probability = root.path("probability_output");
        if ("LIVE_E4".equals(mode) || "SMOKE".equals(mode)) {
            if (!probability.isObject() || probability.path("shape").size()!=3
                    || probability.path("shape").get(0).asInt()!=4
                    || probability.path("shape").get(1).asInt()!=height
                    || probability.path("shape").get(2).asInt()!=width
                    || !"independent_uncalibrated_sigmoid_scores".equals(probability.path("semantics").asText()))
                throw new IllegalArgumentException("Four score grids or score semantics missing");
            requireHash(Path.of(probability.path("path").asText("")),probability.path("sha256").asText());
        } else if (!probability.isNull()) throw new IllegalArgumentException("Fallback cannot claim model scores");
        if (!"flooded_building_or_road_pixels_NOT_continuous_flood_extent".equals(
                root.path("derived_outputs").path("flood_mask").path("meaning").asText()))
            throw new IllegalArgumentException("Flood mask meaning is ambiguous");
        requireHash(Path.of(root.path("derived_outputs").path("flood_mask").path("path").asText("")),
                root.path("derived_outputs").path("flood_mask").path("sha256").asText());
        if (root.path("model_identity").path("name").asText().isBlank())
            throw new IllegalArgumentException("Model identity missing");
        return root;
    }

    public static void requireBridgeReady(JsonNode contract) {
        if (contract == null || !"LIVE_E4".equals(contract.path("execution_mode").asText())
                || !"SPATIAL_VALID".equals(contract.path("validation_status").asText())
                || !contract.path("spatial_reference").isObject())
            throw new IllegalStateException("AI masks have no verified E4 spatial object bridge");
    }

    private static void requireHash(Path path, String expected) throws Exception {
        if (!expected.matches("[0-9a-fA-F]{64}") || !Files.isRegularFile(path))
            throw new IllegalArgumentException("Missing file or SHA-256: " + path);
        MessageDigest sha = MessageDigest.getInstance("SHA-256");
        try (var input = Files.newInputStream(path)) {
            byte[] block = new byte[1 << 20];
            for (int read; (read = input.read(block)) != -1;) sha.update(block, 0, read);
        } catch (IOException error) { throw new IllegalArgumentException("Cannot read: " + path, error); }
        if (!HexFormat.of().formatHex(sha.digest()).equalsIgnoreCase(expected))
            throw new IllegalArgumentException("SHA-256 mismatch: " + path);
    }
}
