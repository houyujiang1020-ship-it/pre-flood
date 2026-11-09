package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class RoadRiskEvidenceTest {
    @TempDir Path temp;
    private Path ledger(String status) throws Exception {
        Path file=temp.resolve("roads.json");
        Files.writeString(file,"""
                {"network_url":"gdbp://net","roads_url":"gdbp://roads","network_edge_count":2,
                 "unlisted_status":"NORMAL","unlisted_evidence":"reviewed all edges",
                 "roads":[{"source_feature_id":"r1","status":"%s","evidence":"field review"}]}
                """.formatted(status));
        return file;
    }
    @Test void exactBlockedIdsAndProvenanceAreRequired() throws Exception {
        var valid=RoadRiskEvidence.verify(ledger("BLOCKED"),"gdbp://roads",Set.of("r1","r2"),Set.of("r1"));
        assertEquals(1,valid.blockedRoads()); assertEquals(64,valid.sha256().length());
        assertThrows(IllegalArgumentException.class,()->RoadRiskEvidence.verify(ledger("FLOODED"),"gdbp://roads",Set.of("r1","r2"),Set.of("r1")));
        assertThrows(IllegalArgumentException.class,()->RoadRiskEvidence.verify(ledger("BLOCKED"),"gdbp://other",Set.of("r1","r2"),Set.of("r1")));
        assertThrows(IllegalArgumentException.class,()->RoadRiskEvidence.verify(ledger("BLOCKED"),"gdbp://roads",Set.of("r2"),Set.of("r1")));
    }
}
