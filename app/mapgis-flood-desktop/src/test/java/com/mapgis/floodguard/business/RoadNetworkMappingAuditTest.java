package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class RoadNetworkMappingAuditTest {
    private static RoadNetworkMappingAudit.Entry road(String id,RoadImpedance.Status status) {
        return new RoadNetworkMappingAudit.Entry(id,status,"field review");
    }
    @Test void oneToManyMappingAndBlockedRoadPass() {
        var result=RoadNetworkMappingAudit.check("v1","v1",2,
                List.of(road("11",RoadImpedance.Status.BLOCKED),road("12",RoadImpedance.Status.FLOODED)),
                Set.of(1,2,3), (dataset,id)->id.equals("11")?List.of(1,2):List.of(3),"gdbp://roads");
        assertTrue(result.routable());
        assertEquals(2,result.mappedRoadCount());
        assertEquals(RoadImpedance.Status.BLOCKED,result.edgeStatuses().get(2));
    }
    @Test void unmappedBlockedRoadCannotPass() {
        var result=RoadNetworkMappingAudit.check("v1","v1",2,
                List.of(road("11",RoadImpedance.Status.NORMAL),road("12",RoadImpedance.Status.BLOCKED)),
                Set.of(1), (dataset,id)->id.equals("11")?List.of(1):List.of(),"gdbp://roads");
        assertFalse(result.routable());
        assertEquals(1,result.unmappedRoadCount());
    }
    @Test void incompleteSourceInventoryCannotPass() {
        var result=RoadNetworkMappingAudit.check("v1","v1",2,
                List.of(road("11",RoadImpedance.Status.NORMAL)),Set.of(1),
                (dataset,id)->List.of(1),"gdbp://roads");
        assertFalse(result.routable());
        assertEquals(1,result.unmappedRoadCount());
    }
    @Test void staleVersionDuplicateOwnershipAndMissingEdgeFail() {
        var result=RoadNetworkMappingAudit.check("old","current",3,
                List.of(road("11",RoadImpedance.Status.NORMAL),road("12",RoadImpedance.Status.BLOCKED),
                        road("12",RoadImpedance.Status.BLOCKED)), Set.of(1,2),
                (dataset,id)->id.equals("11")?List.of(1):List.of(1,9),"gdbp://roads");
        assertFalse(result.routable());
        assertTrue(result.duplicateMappingCount()>0);
        assertTrue(result.missingEdgeCount()>0);
        assertTrue(result.issues().contains("NETWORK_VERSION_MISMATCH"));
    }
}
