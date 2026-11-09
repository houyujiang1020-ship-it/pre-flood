package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class RiskSpatialRulesTest {
    @Test void populationUsesExplicitPersonsPerCellAndClippedArea() {
        assertEquals(25, RiskSpatialRules.allocatedPopulation(100,"persons_per_cell",100,25,"cell"),1e-12);
        assertEquals(0, RiskSpatialRules.allocatedPopulation(0,"persons_per_cell",100,25,"cell"));
        assertThrows(IllegalArgumentException.class,()->RiskSpatialRules.allocatedPopulation(100,"persons_per_km2",100,25,"cell"));
        assertThrows(IllegalArgumentException.class,()->RiskSpatialRules.allocatedPopulation(100,null,100,25,"cell"));
        assertThrows(IllegalArgumentException.class,()->RiskSpatialRules.allocatedPopulation(100,"persons_per_cell",100,120,"cell"));
    }
    @Test void buildingCrossingZoneIsAssignedOnlyOnce() {
        assertEquals("A",RiskSpatialRules.owner(Map.of("A",60.0,"B",40.0),"b1"));
        assertNull(RiskSpatialRules.owner(Map.of("A",0.0,"B",0.0),"b2"));
        assertThrows(IllegalArgumentException.class,()->RiskSpatialRules.owner(Map.of("A",50.0,"B",50.0),"b3"));
    }
    @Test void rejectsCrsMismatchAndDuplicateIds() {
        RiskSpatialRules.requireSameCrs("PROJCS[A]",Map.of("roads","PROJCS[A]"));
        assertThrows(IllegalArgumentException.class,()->RiskSpatialRules.requireSameCrs("PROJCS[A]",Map.of("roads","PROJCS[B]")));
        Set<String> ids=new HashSet<>(); RiskSpatialRules.requireUnique("r1","road",ids);
        assertThrows(IllegalArgumentException.class,()->RiskSpatialRules.requireUnique("r1","road",ids));
    }
}
