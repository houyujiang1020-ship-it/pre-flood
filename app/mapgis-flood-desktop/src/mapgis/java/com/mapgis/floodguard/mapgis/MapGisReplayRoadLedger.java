package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.zondy.mapgis.geodatabase.net.NetCls;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/** Binds the explicitly simulated road states to the network just created from those roads. */
final class MapGisReplayRoadLedger {
    private static final ObjectMapper JSON=new ObjectMapper();
    private MapGisReplayRoadLedger() {}

    static Path create(Path draftPath,Path networkEvidence,NetCls network) throws Exception {
        JsonNode draft=JSON.readTree(draftPath.toFile());
        JsonNode build=JSON.readTree(networkEvidence.toFile());
        Path source=networkEvidence.getParent().getParent().resolve("network-source/manifest.json");
        JsonNode manifest=JSON.readTree(source.toFile());
        if (!draft.path("simulation_only").asBoolean() || draft.path("native_mapping_verified").asBoolean()
                || !draft.path("source_road_sha256").asText().equals(manifest.path("source_utm32_roads_sha256").asText())
                || !build.path("source_sha256").asText().equals(manifest.path("files").path("roads.geojson").asText())
                || !build.path("native_network_created").asBoolean()
                || !network.hasOpened() || !network.getURL().equals(build.path("network_url").asText()))
            throw new IllegalArgumentException("模拟道路状态与当前原生路网版本不一致");
        JsonNode nativeIds=build.path("source_feature_ids"), edges=build.path("source_edge_ids");
        if (!nativeIds.isObject() || !edges.isObject() || draft.path("roads").size()!=nativeIds.size())
            throw new IllegalArgumentException("源道路 OID 或边映射不完整");
        List<Map<String,Object>> rows=new ArrayList<>(); Set<Long> seenOids=new HashSet<>();
        for (JsonNode road:draft.path("roads")) {
            String id=road.path("source_road_id").asText();
            long oid=nativeIds.path(id).asLong(-1);
            JsonNode mapped=edges.path(id);
            String status=road.path("status").asText();
            if (oid<=0 || !seenOids.add(oid) || !mapped.isArray() || mapped.isEmpty()
                    || !Set.of("NORMAL","BLOCKED").contains(status))
                throw new IllegalArgumentException("模拟道路缺少唯一 OID、边映射或有效状态："+id);
            Map<String,Object> row=new LinkedHashMap<>();
            row.put("source_feature_id",Long.toString(oid)); row.put("original_source_road_id",id);
            row.put("status",status); row.put("simulation_only",true);
            row.put("evidence",road.path("status_source").asText()+"; original_id="+id);
            row.put("expected_native_edges",JSON.convertValue(mapped,List.class));
            rows.add(row);
        }
        String fingerprint=MapGisNetworkFingerprint.calculate(network);
        Map<String,Object> ledger=new LinkedHashMap<>();
        ledger.put("schema_version",1); ledger.put("case_id",draft.path("case_id").asText());
        ledger.put("simulation_only",true); ledger.put("ledger_generated_at",Instant.now().toString());
        ledger.put("status_time",null); ledger.put("status_time_basis","exercise design; no observed closure time");
        ledger.put("source_road_sha256",draft.path("source_road_sha256").asText());
        ledger.put("network_source_sha256",build.path("source_sha256").asText());
        ledger.put("network_url",network.getURL()); ledger.put("roads_url",build.path("roads_url").asText());
        ledger.put("network_fingerprint_sha256",fingerprint);
        ledger.put("network_edge_count",network.getEdgeCount());
        ledger.put("source_road_count",rows.size());
        ledger.put("unlisted_status","NORMAL");
        ledger.put("unlisted_evidence","All simulation source roads are explicitly listed; no operational survey claimed");
        ledger.put("roads",rows);
        Path output=networkEvidence.getParent().resolve("road-status-ledger.json");
        Files.writeString(output,JSON.writerWithDefaultPrettyPrinter().writeValueAsString(ledger),
                StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
        return output;
    }
}
