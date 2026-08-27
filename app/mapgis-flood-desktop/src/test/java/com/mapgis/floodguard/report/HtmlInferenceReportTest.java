package com.mapgis.floodguard.report;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Path;
import java.nio.file.Files;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class HtmlInferenceReportTest {
    @TempDir Path directory;
    private ObjectNode evidence() {
        ObjectNode result = new ObjectMapper().createObjectNode();
        result.put("model_version", "smoke-0.1");
        result.putObject("statistics").put("total_pixels", 100).put("flood_pixels", 35)
                .put("flooded_building_pixels", 25).put("flooded_road_pixels", 10).put("backend", "siamunet-smoke");
        return result;
    }
    @Test void includesActualValuesAndEscapesUntrustedText() throws Exception {
        String html = new HtmlInferenceReport().render("<script>alert(1)</script>", Path.of("灾前.png"), Path.of("灾后.png"), evidence());
        assertFalse(html.contains("<script>"));
        assertTrue(html.contains("&lt;script&gt;"));
        assertTrue(html.contains("<td>35</td>"));
        assertTrue(html.contains("不是已完成的 GIS 灾情报告"));
    }
    @Test void rejectsMissingOrImpossibleCounts() {
        ObjectNode result = evidence();
        ((ObjectNode) result.get("statistics")).put("flood_pixels", 101);
        assertThrows(IllegalArgumentException.class, () -> new HtmlInferenceReport().render("记录", directory, directory, result));
        ((ObjectNode) result.get("statistics")).remove("total_pixels");
        assertThrows(IllegalArgumentException.class, () -> new HtmlInferenceReport().render("记录", directory, directory, result));
    }
    @Test void refusesHtmlDisguisedAsPreview() throws Exception {
        Path preview = directory.resolve("预览.png");
        Files.writeString(preview, "<script>alert(1)</script>");
        ObjectNode result = evidence().put("preview_path", preview.toString());
        assertThrows(java.io.IOException.class, () -> new HtmlInferenceReport().render("记录", directory, directory, result));
    }
}
