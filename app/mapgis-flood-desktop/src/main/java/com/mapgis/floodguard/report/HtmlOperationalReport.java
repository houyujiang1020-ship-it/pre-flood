package com.mapgis.floodguard.report;

import com.mapgis.floodguard.business.*;
import java.time.Instant;

/** Evidence-preserving report for the completed steps, with unknown disaster metrics explicit. */
public final class HtmlOperationalReport {
    public String render(ExposureAssessment.Result exposure, RoadClosurePlan.Result closures,
                         ResourceDispatcher.DispatchPlan plan, DispatchRequest request, String provenance) {
        StringBuilder html = new StringBuilder("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>洪涝业务报告</title>"
                + "<style>body{font-family:Microsoft YaHei,sans-serif;margin:32px;color:#18324a}table{border-collapse:collapse;width:100%}"
                + "td,th{border:1px solid #bbb;padding:8px}pre{white-space:pre-wrap} .warning{background:#fff1cc;padding:14px}</style>"
                + "<h1>洪涝实体核查与资源调度报告</h1><p>" + Instant.now() + "</p>"
                + "<p class='warning'>辅助分析草案，非实际调度指令。模型未达生产精度；相交不等于损毁。"
                + "通行结论来自录入的核查证据，路径仅避开本次登记阻断，不保证现实安全。</p>");
        html.append("<h2>数据与方法</h2><pre>").append(escape(provenance)).append("</pre><p>路网：")
                .append(escape(request.networkUrl())).append("；引擎：MapGIS NetAnalyse；分钟权：")
                .append(escape(request.forwardMinutes()+" / "+request.reverseMinutes()+" / "+request.nodeMinutes()))
                .append("；每网络单位公里数：").append(request.kilometersPerNetworkUnit()).append("</p>");
        html.append("<h2>灾情统计与局限</h2><p>候选建筑：").append(exposure.candidateBuildings())
                .append("；候选道路：").append(exposure.candidateRoads()).append("；登记阻断道路：")
                .append(closures.roads().stream().filter(r -> r.review().status()==RoadClosurePlan.Status.CLOSED).count())
                .append("；阻断网络边：").append(closures.blockedEdges().size()).append("；未核查道路：")
                .append(closures.unreviewed()).append("。</p><p>完整洪水范围、受淹面积、损毁建筑数、受影响人口、社区风险等级：未完成验证，不能填为0。</p>");
        html.append("<h2>实体证据</h2><table><tr><th>数据源</th><th>ID</th><th>类型</th><th>相交斑块</th></tr>");
        for (var e : exposure.entities()) row(html,e.dataset(),e.featureId(),e.kind().toString(),String.join(",",e.patchIds()));
        html.append("</table><h2>道路与网络联动</h2><table><tr><th>道路ID</th><th>核查状态</th><th>证据</th><th>网络边</th></tr>");
        for (var road : closures.roads()) row(html,road.review().featureId(),road.review().status().toString(),road.review().evidence(),road.edgeIds().toString());
        html.append("</table><h2>资源分配建议</h2><p>目的节点：").append(escape(request.destination()))
                .append("；类型：").append(escape(request.type())).append("；需求：").append(plan.requested())
                .append("；未满足：").append(plan.unfulfilled()).append("。未扣减库存，未向外部系统下发。</p>")
                .append("<table><tr><th>资源</th><th>分配容量</th><th>分钟</th><th>公里</th><th>节点</th><th>网络边</th></tr>");
        for (var a : plan.allocations()) {
            var r = a.recommendation(); var route = r.route();
            row(html,r.resource().id(),""+a.assignedCapacity(),""+route.estimatedMinutes(),""+route.distanceKm(),route.nodes().toString(),route.roadIds().toString());
        }
        return html.append("</table><h2>验收边界</h2><p>本报告记录本次业务调用；不代表地图渲染、全部原生测试或模型精度验收通过。"
                + "报告及JSON应与spatial-result.json和原始影像一起保存。</p></html>").toString();
    }
    private static void row(StringBuilder html, String... cells) {
        html.append("<tr>"); for (String cell : cells) html.append("<td>").append(escape(cell)).append("</td>"); html.append("</tr>");
    }
    private static String escape(String text) { return text==null ? "" : text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\"","&quot;"); }
}
