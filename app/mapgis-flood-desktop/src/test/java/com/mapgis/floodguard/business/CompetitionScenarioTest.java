package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class CompetitionScenarioTest {
    @TempDir Path temp;
    @Test void refusesUnpreparedCaseBeforeAnyMapgisCall() throws Exception {
        Path manifest=Files.writeString(temp.resolve("case.json"),"{\"ready\":false,\"data_type\":\"REAL\"}");
        assertThrows(IllegalArgumentException.class,()->new CompetitionScenario().load(manifest));
    }
    @Test void declaredReadyCannotSkipSourceAndSpatialEvidence() throws Exception {
        Path manifest=Files.writeString(temp.resolve("declared-ready.json"),
                "{\"ready\":true,\"data_type\":\"REAL\",\"scenario\":{\"schemaVersion\":1,"
                +"\"name\":\"case\",\"simulated\":false,\"aiMode\":\"REPLAY\","
                +"\"preImage\":\"pre.tif\",\"postImage\":\"post.tif\",\"predictionJson\":\"prediction.json\","
                +"\"administrativeUrl\":\"gdbp://area\",\"populationUrl\":\"gdbp://pop\","
                +"\"floodExtentUrl\":\"gdbp://flood\",\"networkUrl\":\"gdbp://net\","
                +"\"sourceRoadsUrl\":\"gdbp://roads\",\"resourceManifest\":\"resources.json\","
                +"\"roadStatusLedger\":\"road-status.json\",\"startResourceId\":\"a\","
                +"\"targetResourceId\":\"b\",\"areaNameField\":\"name\","
                +"\"resourceRiskField\":\"resource_distance_risk\",\"speedKph\":30},\"sources\":{}}");
        assertThrows(IllegalArgumentException.class,()->new CompetitionScenario().load(manifest));
    }
}
