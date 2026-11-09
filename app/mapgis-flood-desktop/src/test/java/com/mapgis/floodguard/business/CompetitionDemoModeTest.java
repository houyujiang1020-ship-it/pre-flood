package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class CompetitionDemoModeTest {
    private final Path bundle=Path.of(System.getProperty("user.dir"),"../../DemoDataset_Final").normalize();
    @Test void bundledObjectsPassContractButScenarioFailsClosedUntilNativeDataReady() throws Exception {
        var prediction=DamagePrediction.read(bundle.resolve("01_flood_prediction.json"));
        assertEquals(7,prediction.features().size());
        var config=new ObjectMapper().readTree(bundle.resolve("06_scenario.json").toFile());
        assertFalse(config.path("ready").asBoolean());
        assertThrows(IllegalStateException.class,()->new CompetitionDemoMode().loadReadyScenario(
                bundle.resolve("06_scenario.json")));
    }
}
