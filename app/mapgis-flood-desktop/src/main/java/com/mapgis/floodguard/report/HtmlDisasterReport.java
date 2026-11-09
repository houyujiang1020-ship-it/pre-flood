package com.mapgis.floodguard.report;

import com.mapgis.floodguard.business.DamageSummary;
import com.mapgis.floodguard.business.EmergencyRouter.RouteResult;
import java.time.Instant;

public final class HtmlDisasterReport {
    public String render(String eventName, DamageSummary damage, RouteResult route, String modelVersion) {
        return """
            <!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>%s</title>
            <style>body{font-family:'Microsoft YaHei',sans-serif;max-width:900px;margin:40px auto;color:#18324a}table{border-collapse:collapse;width:100%%}td,th{border:1px solid #ccd6df;padding:10px}h1{color:#075985}</style></head><body>
            <h1>%s 灾情报告</h1><p>生成时间：%s</p><h2>灾损统计</h2><table>
            <tr><th>受淹面积</th><td>%.3f km²</td></tr><tr><th>受灾建筑</th><td>%d 栋</td></tr>
            <tr><th>受灾道路 / 阻断</th><td>%d / %d 条</td></tr><tr><th>影响社区</th><td>%d 个</td></tr>
            <tr><th>估算影响人口</th><td>%d 人</td></tr></table><h2>候选救援路线（须现场核实）</h2>
            <p>节点：%s；距离 %.2f km；预计 %.1f 分钟。</p><h2>模型信息</h2><p>%s</p></body></html>
            """.formatted(escape(eventName), escape(eventName), Instant.now(), damage.floodedAreaKm2(),
                damage.floodedBuildings(), damage.floodedRoads(), damage.blockedRoads(), damage.affectedCommunities(),
                damage.affectedPopulation(), escape(String.join(" → ", route.nodes())), route.distanceKm(),
                route.estimatedMinutes(), escape(modelVersion));
    }

    private static String escape(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }
}
