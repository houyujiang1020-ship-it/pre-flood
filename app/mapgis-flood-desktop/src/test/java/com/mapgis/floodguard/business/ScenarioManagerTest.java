package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class ScenarioManagerTest {
    @TempDir Path temp;
    @Test void caseLifecycleNeverDeletesInputs() throws Exception {
        ScenarioManager manager=new ScenarioManager(temp.resolve("cases"));
        Path source=Files.writeString(temp.resolve("source.json"),"source");
        var scenario=new ScenarioManager.Scenario(1,"城市洪涝灾害模拟案例01",true,"REPLAY",
                "pre.tif","post.tif",source.toString(),"a","p","f","n","r","resources","ledger",
                "vehicle","shelter","area_name","resource_distance_risk",30);
        Path saved=manager.save(scenario);
        assertEquals(scenario,manager.load(saved));
        assertEquals(1,manager.list().size());
        assertTrue(scenario.missingForFullRun().isEmpty());
        assertThrows(IllegalArgumentException.class,()->manager.delete(source));
        manager.delete(saved);
        assertTrue(Files.isRegularFile(source));
    }
}
