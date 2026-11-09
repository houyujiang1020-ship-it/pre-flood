package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;

/** Loads a self-contained, validated competition scenario; refuses incomplete bundles. */
public final class CompetitionDemoMode {
    private final ObjectMapper json=new ObjectMapper();
    public ScenarioManager.Scenario loadReadyScenario(Path configuration) throws Exception {
        if (!Files.isRegularFile(configuration)) throw new IllegalArgumentException("缺少比赛演示案例："+configuration);
        var data=json.readTree(configuration.toFile());
        if (!data.path("ready").asBoolean(false))
            throw new IllegalStateException("内置数据集尚未完成 MapGIS 原生准备："+
                    data.path("readiness_reason").asText("请查看 06_scenario.json"));
        var scenario=json.treeToValue(data.path("scenario"),ScenarioManager.Scenario.class);
        if (scenario.missingForFullRun().size()>0)
            throw new IllegalStateException("比赛演示案例缺少："+String.join("、",scenario.missingForFullRun()));
        return scenario;
    }
}
