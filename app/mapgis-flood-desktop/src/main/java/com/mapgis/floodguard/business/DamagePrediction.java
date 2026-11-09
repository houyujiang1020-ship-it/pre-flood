package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/** Strict handoff contract from object predictions to native MapGIS feature classes. */
public final class DamagePrediction {
    public enum ClassId { BUILDING_NORMAL, BUILDING_FLOODED, ROAD_NORMAL, ROAD_FLOODED, ROAD_BLOCKED }
    public record Feature(String objectId, ClassId category, JsonNode geometry,
                          double damageProbability, String floodStatus) {}
    public record Dataset(String crsWkt, List<Feature> features) {}
    private static final ObjectMapper JSON = new ObjectMapper();
    private DamagePrediction() {}

    public static Dataset read(Path file) throws IOException {
        if (!Files.isRegularFile(file) || Files.size(file) > 16_000_000)
            throw new IllegalArgumentException("缺少 flood_prediction.json 或文件超过 16 MB");
        JsonNode root = JSON.readTree(file.toFile());
        if (root == null || !root.isObject()) throw new IllegalArgumentException("预测文件须为 JSON 对象");
        String crs = text(root, "crs_wkt");
        // Area in square metres is meaningful only for a declared metre-based projection.
        if (!crs.startsWith("PROJCS[") || !crs.toLowerCase(Locale.ROOT).contains("unit[\"metre\""))
            throw new IllegalArgumentException("须提供米制投影的 crs_wkt，才能计算建筑面积");
        JsonNode objects = root.path("objects");
        if (!objects.isArray() || objects.isEmpty() || objects.size() > 100_000)
            throw new IllegalArgumentException("objects 必须含 1 至 100000 个对象");
        Set<String> ids = new HashSet<>();
        List<Feature> features = new ArrayList<>();
        for (JsonNode object : objects) {
            String id = text(object, "object_id");
            if (id.length() > 80 || !ids.add(id)) throw new IllegalArgumentException("对象编号重复或过长：" + id);
            String type = text(object, "type").toLowerCase(Locale.ROOT);
            String status = text(object, "flood_status").toLowerCase(Locale.ROOT);
            JsonNode probability = object.path("damage_probability");
            if (!probability.isNumber() || !Double.isFinite(probability.asDouble())
                    || probability.asDouble() < 0 || probability.asDouble() > 1)
                throw new IllegalArgumentException(id + " 的 damage_probability 须介于 0 和 1");
            ClassId category = switch (type + ":" + status) {
                case "building:normal", "building:not_flooded" -> ClassId.BUILDING_NORMAL;
                case "building:flooded" -> ClassId.BUILDING_FLOODED;
                case "road:normal" -> ClassId.ROAD_NORMAL;
                case "road:flooded" -> ClassId.ROAD_FLOODED;
                case "road:blocked" -> ClassId.ROAD_BLOCKED;
                default -> throw new IllegalArgumentException(id + " 的类型/状态组合不支持；道路阻断须明确标注 blocked");
            };
            JsonNode geometry = object.path("geometry");
            String expected = type.equals("building") ? "Polygon" : "LineString";
            if (!expected.equals(geometry.path("type").asText()))
                throw new IllegalArgumentException(id + " 需要 " + expected + " GeoJSON 几何");
            validateCoordinates(geometry.path("coordinates"), id, expected.equals("Polygon"));
            features.add(new Feature(id, category, geometry.deepCopy(), probability.asDouble(), status));
        }
        return new Dataset(crs, List.copyOf(features));
    }
    private static String text(JsonNode node, String name) {
        if (node == null || !node.path(name).isTextual() || node.path(name).asText().isBlank())
            throw new IllegalArgumentException("缺少字段 " + name);
        return node.path(name).asText().trim();
    }
    private static void validateCoordinates(JsonNode coordinates, String id, boolean polygon) {
        if (!coordinates.isArray() || coordinates.isEmpty()) throw new IllegalArgumentException(id + " 坐标为空");
        if (polygon) {
            for (JsonNode ring : coordinates) {
                if (!ring.isArray() || ring.size() < 4 || !ring.get(0).equals(ring.get(ring.size()-1)))
                    throw new IllegalArgumentException(id + " 多边形环未闭合");
                for (JsonNode point : ring) point(point, id);
            }
        } else {
            if (coordinates.size() < 2) throw new IllegalArgumentException(id + " 道路至少需要两个点");
            for (JsonNode point : coordinates) point(point, id);
        }
    }
    private static void point(JsonNode point, String id) {
        if (!point.isArray() || point.size() != 2 || !point.get(0).isNumber() || !point.get(1).isNumber()
                || !Double.isFinite(point.get(0).asDouble()) || !Double.isFinite(point.get(1).asDouble()))
            throw new IllegalArgumentException(id + " 坐标必须是有限的 [x,y]");
    }
    public static String severity(Feature feature) {
        if (feature.category() == ClassId.BUILDING_NORMAL || feature.category() == ClassId.ROAD_NORMAL) return "无";
        return feature.damageProbability() >= 0.8 ? "高" : feature.damageProbability() >= 0.5 ? "中" : "低";
    }
    public static void main(String[] args) throws Exception {
        if (args.length!=1) throw new IllegalArgumentException("flood_prediction.json required");
        Dataset dataset=read(Path.of(args[0]));
        System.out.println("REPLAY prediction parsed: "+dataset.features().size()+" objects; crs="+dataset.crsWkt());
    }
}
