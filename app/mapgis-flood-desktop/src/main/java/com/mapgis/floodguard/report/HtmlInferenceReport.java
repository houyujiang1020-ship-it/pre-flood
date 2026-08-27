package com.mapgis.floodguard.report;

import com.fasterxml.jackson.databind.JsonNode;
import java.nio.file.Files;
import java.nio.file.Path;
import java.io.IOException;
import java.time.Instant;
import java.util.Base64;

/** Reports actual inference evidence; never invents GIS area, object counts or routes. */
public final class HtmlInferenceReport {
    public String render(String event, Path pre, Path post, JsonNode result) throws IOException {
        if (result == null || !result.isObject()) throw new IllegalArgumentException("Missing inference result");
        JsonNode statistics = result.path("statistics");
        long total = count(statistics, "total_pixels"), flooded = count(statistics, "flood_pixels");
        long buildings = count(statistics, "flooded_building_pixels"), roads = count(statistics, "flooded_road_pixels");
        if (total == 0 || flooded > total || buildings > total || roads > total)
            throw new IllegalArgumentException("Inconsistent pixel counts");
        String preview = "<p>预览未提供。</p>";
        String previewPath = result.path("preview_path").asText("");
        if (!previewPath.isBlank()) {
            Path path = Path.of(previewPath);
            if (!Files.isRegularFile(path) || Files.size(path) > 8 * 1024 * 1024)
                throw new IOException("Preview missing or exceeds 8 MB");
            byte[] bytes = Files.readAllBytes(path);
            byte[] signature = {(byte)137, 80, 78, 71, 13, 10, 26, 10};
            if (bytes.length < signature.length || !java.util.Arrays.equals(signature, java.util.Arrays.copyOf(bytes, 8)))
                throw new IOException("Only PNG previews may be embedded");
            preview = "<img alt=\"模型像素预览，非核验专题地图\" src=\"data:image/png;base64," + Base64.getEncoder().encodeToString(bytes) + "\">";
        }
        return """
            <!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>%s</title>
            <style>body{font-family:'Microsoft YaHei',sans-serif;max-width:980px;margin:36px auto;padding:0 20px;color:#18324a}table{border-collapse:collapse;width:100%%}th,td{border:1px solid #ccd6df;padding:10px;text-align:left}img{max-width:100%%}.warning{background:#fff4d5;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body>
            <h1>%s · 模型识别记录</h1><p>生成时间：%s</p>
            <p class="warning">开发验证输出，模型精度未经认可，不可直接用于真实应急决策。像素数不等于建筑栋数、路段数或地理面积。本记录不是已完成的 GIS 灾情报告。</p>
            <h2>输入与模型</h2><p>灾前：%s</p><p>灾后：%s</p><p>后端：%s；模型版本：%s</p>
            <h2>实际像素统计</h2><table><tr><th>指标</th><th>像素数</th></tr>
            <tr><td>影像总像素</td><td>%d</td></tr><tr><td>受淹掩膜</td><td>%d</td></tr>
            <tr><td>受淹建筑候选像素</td><td>%d</td></tr><tr><td>受淹道路候选像素</td><td>%d</td></tr></table>
            <p>烟测模型的受淹掩膜仅为受淹建筑/道路并集，不能代表完整水面范围。</p>
            <h2>模型预览</h2>%s<h2>尚未完成的空间业务</h2>
            <p>实际面积、建筑/道路数量、人口影响、安全路线和资源调度须经 MapGIS 空间计算及核验后另行报告。这里不填充演示数字。</p>
            <h2>服务返回原始证据</h2><pre>%s</pre></body></html>
            """.formatted(escape(event), escape(event), Instant.now(), escape(pre.toString()), escape(post.toString()),
                    escape(statistics.path("backend").asText("unknown")), escape(result.path("model_version").asText("unknown")),
                    total, flooded, buildings, roads, preview, escape(result.toPrettyString()));
    }

    private static long count(JsonNode statistics, String name) {
        JsonNode value = statistics.path(name);
        if (!value.isIntegralNumber() || !value.canConvertToLong() || value.asLong() < 0)
            throw new IllegalArgumentException("Invalid pixel count: " + name);
        return value.asLong();
    }
    private static String escape(String value) {
        return java.util.Objects.requireNonNull(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }
}
