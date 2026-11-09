package com.mapgis.floodguard.business;
import com.mapgis.floodguard.report.HtmlExposureReport;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
class ExposureAssessmentTest {
    private ExposureAssessment.Hit hit(String dataset,String id,String patch) {
        return new ExposureAssessment.Hit(dataset,id,ExposureAssessment.Kind.BUILDING,patch);
    }
    @Test void deduplicatesOverlappingPatchesButKeepsDatasetIdentity() {
        var result = new ExposureAssessment().aggregate(List.of(hit("A","1","p1"),hit("A","1","p2"),hit("A","1","p1"),hit("B","1","p1")));
        assertEquals(2,result.candidateBuildings()); assertEquals(0,result.candidateRoads());
        assertEquals(2,result.entities().get(0).patchIds().size());
    }
    @Test void reportEscapesDataAndDoesNotClaimConfirmedDamage() {
        var result = new ExposureAssessment().aggregate(List.of(hit("<script>","1","p1")));
        String html = new HtmlExposureReport().render("<event>",result,"MapGIS测试来源");
        assertFalse(html.contains("<script>")); assertTrue(html.contains("&lt;script&gt;"));
        assertTrue(html.contains("尚未计算")); assertTrue(html.contains("不代表已确认"));
    }
    @Test void rejectsMissingEntityId() { assertThrows(IllegalArgumentException.class, () -> hit("A","","p1")); }
}
