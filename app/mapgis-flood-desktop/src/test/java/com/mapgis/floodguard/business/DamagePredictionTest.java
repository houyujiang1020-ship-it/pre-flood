package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class DamagePredictionTest {
    private static final String CRS = "PROJCS[\\\"UTM 32N\\\",UNIT[\\\"metre\\\",1]]";
    private static final String ROAD = "{\"object_id\":\"R1\",\"type\":\"road\",\"geometry\":{\"type\":\"LineString\",\"coordinates\":[[1,2],[3,4]]},\"damage_probability\":0.9,\"flood_status\":\"blocked\"}";
    private Path file(String object, String crs) throws Exception {
        Path path = Files.createTempFile("damage-prediction-", ".json");
        Files.writeString(path, "{\"crs_wkt\":\"" + crs + "\",\"objects\":[" + object + "]}");
        return path;
    }
    @Test void acceptsFourThematicCategoriesInFixture() throws Exception {
        var dataset = DamagePrediction.read(Path.of("src/test/resources/flood_prediction.fixture.json"));
        assertEquals(4,dataset.features().size());
        assertEquals(4,dataset.features().stream().map(DamagePrediction.Feature::category).distinct().count());
        assertEquals("高",DamagePrediction.severity(dataset.features().get(1)));
        assertEquals("无",DamagePrediction.severity(dataset.features().get(2)));
    }
    @Test void acceptsExplicitBlockedRoadAndKeepsProbabilitySeparate() throws Exception {
        Path path = file(ROAD, CRS);
        try {
            var dataset = DamagePrediction.read(path);
            assertEquals(DamagePrediction.ClassId.ROAD_BLOCKED, dataset.features().get(0).category());
            assertEquals("高", DamagePrediction.severity(dataset.features().get(0)));
        } finally { Files.deleteIfExists(path); }
    }
    @Test void floodedRoadRemainsDistinctFromIndependentClosure() throws Exception {
        Path path = file(ROAD.replace("blocked", "flooded"), CRS);
        try { assertEquals(DamagePrediction.ClassId.ROAD_FLOODED, DamagePrediction.read(path).features().get(0).category()); }
        finally { Files.deleteIfExists(path); }
    }
    @Test void requiresProjectedMetreCrsAndValidProbability() throws Exception {
        Path geographic = file(ROAD, "GEOGCS[\\\"WGS84\\\"]");
        Path invalid = file(ROAD.replace("0.9", "1.4"), CRS);
        try {
            assertThrows(IllegalArgumentException.class, () -> DamagePrediction.read(geographic));
            assertThrows(IllegalArgumentException.class, () -> DamagePrediction.read(invalid));
        } finally { Files.deleteIfExists(geographic); Files.deleteIfExists(invalid); }
    }
}
