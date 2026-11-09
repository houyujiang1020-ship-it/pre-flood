package com.mapgis.floodguard.report;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class ReportGeneratorTest {
    @TempDir Path temp;
    @Test void rejectsIncompleteRiskAndEscapesUntrustedNames() throws Exception {
        Path ai=Files.writeString(temp.resolve("ai.json"),"{\"mode\":\"REPLAY\",\"source\":\"archived\",\"status\":\"COMPLETE\"}");
        Path damage=Files.writeString(temp.resolve("damage.json"),"{\"counts\":{\"BUILDING_FLOODED\":1}}");
        Path risk=Files.writeString(temp.resolve("risk.json"),"{\"status\":\"PARTIAL\",\"areas\":[{\"area\":\"A\"}]}");
        Path route=Files.writeString(temp.resolve("route.json"),"{\"start\":\"V\",\"target\":\"S\",\"optimized\":{},\"distance\":100,\"time\":2,\"risk_level\":\"LOW\"}");
        Path resources=Files.writeString(temp.resolve("resources.json"),"{\"recommendations\":[\"vehicle\"]}");
        var generator=new ReportGenerator();
        var evidence=new ReportGenerator.Evidence("<script>alert(1)</script>",true,ai,damage,risk,route,resources,1000,Map.of());
        assertThrows(IllegalStateException.class,()->generator.generate(evidence,temp.resolve("incomplete")));
        Files.writeString(risk,"{\"status\":\"COMPLETE\",\"areas\":[{\"area\":\"A\",\"riskLevel\":\"LOW\",\"riskScore\":0.2,\"affectedPopulation\":5}]}");
        Path report=generator.generate(evidence,temp.resolve("complete"));
        String html=Files.readString(report);
        assertTrue(html.contains("&lt;script&gt;"));
        assertFalse(html.contains("<script>"));
        assertTrue(html.contains("结果回放"));
    }
}
