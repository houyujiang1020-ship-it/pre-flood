package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class ResultValidatorTest {
    @TempDir Path temp;
    @Test void checksNumbersButNeverClaimsIndependentSpatialAcceptance() throws Exception {
        Path damage=Files.writeString(temp.resolve("damage.json"),
                "{\"status\":\"native_mapgis_layers_loaded\",\"counts\":{\"BUILDING_NORMAL\":3,\"BUILDING_FLOODED\":1,\"ROAD_NORMAL\":4,\"ROAD_BLOCKED\":1}}");
        Path risk=Files.writeString(temp.resolve("risk.json"),
                "{\"engine\":\"MapGIS\",\"status\":\"COMPLETE\",\"areas\":[{"+
                "\"area\":\"A\",\"totalBuildings\":4,\"damagedBuildings\":1,\"buildingRisk\":0.25,"+
                "\"totalPopulation\":100,\"affectedPopulation\":20,\"populationRisk\":0.2,"+
                "\"totalRoadMetres\":1000,\"blockedRoadMetres\":200,\"blockedRoads\":1,\"roadRisk\":0.2,"+
                "\"resourceDistanceRisk\":0.4,\"riskScore\":0.24}]}");
        Path route=Files.writeString(temp.resolve("route.json"),
                "{\"network_url\":\"gdbp://MapGIS/FG/network\",\"distance\":500,"+
                "\"road_count\":2,\"optimized\":{\"distanceMetres\":500,\"edges\":[1,2]}}");
        Path output=new ResultValidator().validate(damage,risk,route,temp.resolve("validation_result.json"));
        var report=new ObjectMapper().readTree(output.toFile());
        assertTrue(report.path("cross_evidence_consistent").asBoolean());
        assertEquals("NOT_VERIFIED",report.path("final_acceptance").asText());
        Files.writeString(route,"{\"network_url\":\"gdbp://MapGIS/FG/network\",\"distance\":400,"+
                "\"road_count\":2,\"optimized\":{\"distanceMetres\":500,\"edges\":[1,2]}}");
        new ResultValidator().validate(damage,risk,route,output);
        assertEquals("FAIL",new ObjectMapper().readTree(output.toFile()).path("checks").path("route_arithmetic").asText());
    }
}
