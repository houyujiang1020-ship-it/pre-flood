package com.mapgis.floodguard.report;

import static org.junit.jupiter.api.Assertions.*;
import com.mapgis.floodguard.business.DamageSummary;
import com.mapgis.floodguard.business.EmergencyRouter.RouteResult;
import java.util.List;
import org.junit.jupiter.api.Test;

class HtmlDisasterReportTest {
    @Test void rendersRealValuesAndEscapesUserText() {
        String html = new HtmlDisasterReport().render("武汉<洪涝>", new DamageSummary(12.7, 1342, 87, 31, 12, 28463),
                new RouteResult(List.of("消防站", "社区"), List.of("R1"), 8.2, 16.4), "spectral-change-fallback");
        assertTrue(html.contains("12.700 km²")); assertTrue(html.contains("28463 人"));
        assertTrue(html.contains("武汉&lt;洪涝&gt;")); assertFalse(html.contains("武汉<洪涝>"));
    }
}
