package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Checks that every blocked source road is supported by the same case's status ledger. */
public final class RoadRiskEvidence {
    public record Verified(Path path,String sha256,String sourceRoadsUrl,int reviewedRoads,int blockedRoads) {}
    private RoadRiskEvidence() {}
    public static Verified verify(Path path,String sourceRoadsUrl,Set<String> allRoadIds,Set<String> blockedIds) throws Exception {
        if (path==null || !Files.isRegularFile(path) || Files.size(path)>5_000_000)
            throw new IllegalArgumentException("道路状态核查单缺失或过大");
        if (sourceRoadsUrl==null || !sourceRoadsUrl.startsWith("gdbp://"))
            throw new IllegalArgumentException("原始道路图层 URL 缺失");
        JsonNode root=new ObjectMapper().readTree(path.toFile());
        if (!sourceRoadsUrl.equals(root.path("roads_url").asText())
                || !root.path("network_url").asText().startsWith("gdbp://")
                || root.path("network_edge_count").asLong(0)<=0
                || !"NORMAL".equals(root.path("unlisted_status").asText())
                || root.path("unlisted_evidence").asText().isBlank()
                || !root.path("roads").isArray())
            throw new IllegalArgumentException("道路核查单与原始道路/路网或全网状态证据不一致");
        Set<String> reviewed=new HashSet<>(), ledgerBlocked=new HashSet<>();
        for (JsonNode road:root.path("roads")) {
            String id=road.path("source_feature_id").asText();
            String status=road.path("status").asText();
            if (id.isBlank() || !allRoadIds.contains(id) || !reviewed.add(id)
                    || road.path("evidence").asText().isBlank()
                    || !Set.of("NORMAL","FLOODED","HIGH_RISK","BLOCKED").contains(status))
                throw new IllegalArgumentException("道路核查对象 ID、状态或证据无效："+id);
            if ("BLOCKED".equals(status)) ledgerBlocked.add(id);
        }
        if (!ledgerBlocked.equals(blockedIds))
            throw new IllegalArgumentException("阻断道路图层与核查单的对象 ID 不一致");
        byte[] bytes=Files.readAllBytes(path);
        return new Verified(path.toAbsolutePath().normalize(),HexFormat.of().formatHex(
                MessageDigest.getInstance("SHA-256").digest(bytes)),sourceRoadsUrl,reviewed.size(),ledgerBlocked.size());
    }
}
