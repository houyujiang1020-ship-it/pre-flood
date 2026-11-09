package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;

class DemoControllerTest {
    @TempDir Path temp;
    private ScenarioManager.Scenario scenario() {
        return new ScenarioManager.Scenario(1,"演练",true,"REPLAY",
                "pre","post","prediction","area","population","extent","network","roads","resources","ledger",
                "vehicle","shelter","name","resource_distance_risk",30);
    }
    @Test void stopsAtFirstMissingEvidenceAndPersistsFailure() throws Exception {
        var scenario=scenario();
        List<DemoController.Step> called=new ArrayList<>();
        var listener=new DemoController.Listener() {
            public void started(DemoController.Step step,int done,int total) {}
            public void completed(DemoController.Step step,Path path,int done,int total) {}
            public void failed(DemoController.Step step,Throwable error) {}
        };
        var run=new DemoController().start(scenario,temp,(step,s,evidence)->{
            called.add(step);
            if (step==DemoController.Step.DAMAGE_THEMATIC) return CompletableFuture.completedFuture(temp.resolve("missing.json"));
            return CompletableFuture.completedFuture(Files.writeString(temp.resolve(step+".json"),"{}"));
        },listener);
        assertThrows(CompletionException.class,()->run.toCompletableFuture().join());
        assertEquals(List.of(DemoController.Step.LOAD_DATA,DemoController.Step.AI_DETECTION,
                DemoController.Step.DAMAGE_THEMATIC),called);
        try (var dirs=Files.list(temp)) {
            Path ledger=dirs.filter(Files::isDirectory).findFirst().orElseThrow().resolve("demo-progress.json");
            assertTrue(Files.readString(ledger).contains("\"status\" : \"FAILED\""));
        }
    }
    @Test void completeRunRecordsAllEightStageFiles() throws Exception {
        List<DemoController.Step> completed=new ArrayList<>();
        var listener=new DemoController.Listener() {
            public void started(DemoController.Step step,int done,int total) {}
            public void completed(DemoController.Step step,Path path,int done,int total) { completed.add(step); }
            public void failed(DemoController.Step step,Throwable error) { fail(error); }
        };
        var result=new DemoController().start(scenario(),temp,(step,s,evidence)->
                CompletableFuture.completedFuture(Files.writeString(temp.resolve(step+".json"),"{}")),listener)
                .toCompletableFuture().join();
        assertEquals(List.of(DemoController.Step.values()),completed);
        assertEquals(8,result.evidence().size());
        assertTrue(Files.readString(result.ledger()).contains("\"status\" : \"COMPLETE\""));
    }
}
