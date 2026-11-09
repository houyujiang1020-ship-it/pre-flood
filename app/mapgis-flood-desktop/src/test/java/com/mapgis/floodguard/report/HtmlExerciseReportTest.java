package com.mapgis.floodguard.report;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class HtmlExerciseReportTest {
    @Test void escapesUntrustedEvidence() {
        String html=new HtmlExerciseReport().render(false,"<script>alert(1)</script>&");
        assertFalse(html.contains("<script>")); assertTrue(html.contains("&lt;script&gt;"));
        assertTrue(html.contains("未通过"));
    }
    @Test void doesNotClaimOperationalReadiness() {
        String html=new HtmlExerciseReport().render(true,"{}");
        assertTrue(html.contains("正式命名分钟权业务调度仍未验收"));
        assertTrue(html.contains("假设匀速"));
    }
}
