package com.mapgis.floodguard.business;

import java.util.*;

/** Checks a reviewed source-road ledger against the currently opened native network. */
public final class RoadNetworkMappingAudit {
    public record Entry(String sourceId, RoadImpedance.Status status, String evidence) {}
    public record Result(String status, int sourceRoadCount, int mappedRoadCount, int unmappedRoadCount,
                         int duplicateMappingCount, int missingEdgeCount, int ledgerMismatchCount,
                         int ambiguousCount, Map<Integer,RoadImpedance.Status> edgeStatuses,
                         List<String> issues) {
        public boolean routable() { return "PASS".equals(status); }
    }
    private RoadNetworkMappingAudit() {}

    public static Result check(String expectedNetworkVersion, String actualNetworkVersion,
                               int sourceRoadCount, Collection<Entry> entries, Set<Integer> networkEdges,
                               RoadClosurePlan.EdgeResolver resolver, String roadsUrl) {
        Objects.requireNonNull(entries); Objects.requireNonNull(networkEdges); Objects.requireNonNull(resolver);
        List<String> issues=new ArrayList<>();
        Map<Integer,RoadImpedance.Status> mapped=new LinkedHashMap<>();
        Set<String> seen=new HashSet<>();
        int success=0,unmapped=0,duplicates=0,missing=0,mismatch=0,ambiguous=0;
        if (expectedNetworkVersion==null || expectedNetworkVersion.isBlank()
                || !expectedNetworkVersion.equals(actualNetworkVersion))
            issues.add("NETWORK_VERSION_MISMATCH");
        if (sourceRoadCount<0 || entries.size()!=sourceRoadCount) issues.add("SOURCE_COUNT_MISMATCH");
        for (Entry entry:entries) {
            if (entry==null || entry.sourceId()==null || entry.sourceId().isBlank() || entry.status()==null
                    || entry.evidence()==null || entry.evidence().isBlank()) {
                mismatch++; issues.add("INVALID_LEDGER_ENTRY"); continue;
            }
            if (!seen.add(entry.sourceId())) { duplicates++; issues.add("DUPLICATE_SOURCE_ID:"+entry.sourceId()); continue; }
            List<Integer> edges;
            try { edges=resolver.resolve(roadsUrl,entry.sourceId()); }
            catch (RuntimeException error) { unmapped++; issues.add("UNMAPPED:"+entry.sourceId()+":"+error.getMessage()); continue; }
            if (edges==null || edges.isEmpty()) { unmapped++; issues.add("UNMAPPED:"+entry.sourceId()); continue; }
            if (edges.size()!=new HashSet<>(edges).size()) { ambiguous++; issues.add("DUPLICATE_EDGE_IN_SOURCE:"+entry.sourceId()); }
            boolean valid=true;
            for (Integer edge:edges) {
                if (edge==null || !networkEdges.contains(edge)) {
                    missing++; issues.add("MISSING_NETWORK_EDGE:"+entry.sourceId()+":"+edge); valid=false;
                } else if (mapped.containsKey(edge)) {
                    duplicates++; issues.add("EDGE_OWNERSHIP_CONFLICT:"+edge); valid=false;
                }
            }
            if (!valid) continue;
            for (int edge:edges) mapped.put(edge,entry.status());
            success++;
        }
        unmapped=Math.max(unmapped,sourceRoadCount-success);
        String status=issues.isEmpty()?"PASS": mapped.isEmpty()?"FAIL":"PARTIAL";
        return new Result(status,sourceRoadCount,success,unmapped,duplicates,missing,mismatch,ambiguous,
                Map.copyOf(mapped),List.copyOf(issues));
    }
}
