package com.mapgis.floodguard.report;

import com.mapgis.floodguard.business.ExposureAssessment;
import java.time.Instant;
import java.util.Objects;

/** Conservative report: intersection candidates are not confirmed damage or blocked roads. */
public final class HtmlExposureReport {
    public String render(String event, ExposureAssessment.Result result, String sourceDescription) {
        Objects.requireNonNull(result);
        StringBuilder html = new StringBuilder("<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>实体暴露核查</title>");
        html.append("<style>body{font-family:'Microsoft YaHei',sans-serif;margin:32px;color:#18324a}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:8px}</style>");
        html.append("<h1>").append(escape(event)).append(" · 实体暴露核查</h1><p>").append(Instant.now()).append("</p>");
        html.append("<p>来源：").append(escape(sourceDescription)).append("</p><p>预测斑块相交候选：建筑 ")
                .append(result.candidateBuildings()).append("；道路 ").append(result.candidateRoads()).append("。</p>");
        html.append("<p>同一数据集内实体按ID去重。相交（包括边界接触）不代表已确认损毁或道路阻断；面积、人口、阻断数量和安全路线尚未计算。</p>");
        html.append("<table><tr><th>来源数据集</th><th>实体ID</th><th>类型</th><th>命中斑块</th></tr>");
        for (var entity : result.entities()) html.append("<tr><td>").append(escape(entity.dataset())).append("</td><td>")
                .append(escape(entity.featureId())).append("</td><td>").append(entity.kind()).append("</td><td>")
                .append(escape(String.join(", ", entity.patchIds()))).append("</td></tr>");
        return html.append("</table><p>研究验证结果，不用于实际应急指挥。</p></html>").toString();
    }
    private static String escape(String text) {
        return Objects.requireNonNull(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }
}
