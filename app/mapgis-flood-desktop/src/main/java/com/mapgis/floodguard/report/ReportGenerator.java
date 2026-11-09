package com.mapgis.floodguard.report;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.util.*;

/** Renders a final report only from persisted, complete stage evidence. */
public final class ReportGenerator {
    public record Evidence(String scenarioName,boolean simulated,Path aiEvidence,Path damageManifest,
                           Path riskReport,Path routeReport,Path resourceRecommendations,
                           double floodAreaSquareMetres,Map<String,Path> screenshots) {}
    private final ObjectMapper json=new ObjectMapper();
    public Path generate(Evidence evidence,Path outputDirectory) throws Exception {
        Objects.requireNonNull(evidence);
        if (evidence.scenarioName()==null || evidence.scenarioName().isBlank()
                || !Double.isFinite(evidence.floodAreaSquareMetres()) || evidence.floodAreaSquareMetres()<0)
            throw new IllegalArgumentException("案例名称或 MapGIS 灾害面积无效");
        JsonNode ai=read(evidence.aiEvidence()),damage=read(evidence.damageManifest()),
                risk=read(evidence.riskReport()),route=read(evidence.routeReport()),
                resources=read(evidence.resourceRecommendations());
        if (!"COMPLETE".equals(risk.path("status").asText()) || risk.path("areas").isEmpty()
                || !route.path("optimized").isObject() || !resources.path("recommendations").isArray())
            throw new IllegalStateException("综合报告缺少已完成的风险、路线或资源匹配结果");
        if (!"LIVE_AI".equals(ai.path("mode").asText()) && !"REPLAY".equals(ai.path("mode").asText()))
            throw new IllegalStateException("AI 阶段证据必须标明实时推理或回放模式");
        if (!damage.path("counts").isObject()) throw new IllegalStateException("灾损专题证据缺少分类数量");
        Path directory=Files.createDirectories(outputDirectory);
        Path images=Files.createDirectories(directory.resolve("images"));
        Map<String,String> imageNames=new LinkedHashMap<>();
        if (evidence.screenshots()!=null) for (var item:evidence.screenshots().entrySet()) {
            Path source=item.getValue();
            if (source==null || !Files.isRegularFile(source) || Files.size(source)==0) continue;
            String filename=source.getFileName().toString();
            if (!filename.toLowerCase(Locale.ROOT).endsWith(".png")) continue;
            Files.copy(source,images.resolve(filename),StandardCopyOption.REPLACE_EXISTING);
            imageNames.put(item.getKey(),"images/"+filename);
        }
        StringBuilder html=new StringBuilder("<!doctype html><html lang='zh-CN'><meta charset='utf-8'>")
                .append("<title>FloodGuard 综合分析报告</title><style>body{font-family:'Microsoft YaHei',sans-serif;max-width:1100px;margin:32px auto;color:#18334b;line-height:1.5}h1,h2{color:#0c5b83}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #c7d7e3;padding:7px;text-align:left}th{background:#e9f2f7}img{max-width:100%;border:1px solid #a9bdc9;margin:8px 0}.badge{padding:6px;background:#fff4d6}</style><body>")
                .append("<h1>MapGIS-FloodGuard 洪涝灾害智能分析与应急决策报告</h1>")
                .append("<p>案例：").append(esc(evidence.scenarioName())).append("</p>")
                .append("<p class='badge'>").append(evidence.simulated()?"模拟演练数据；不代表实际灾情。":"业务数据；仍须现场核验。")
                .append(" AI 阶段：").append(ai.path("mode").asText().equals("REPLAY")?"结果回放":"实时模型推理").append("。</p>")
                .append("<h2>项目背景</h2><p>面向城市洪涝灾害，将遥感检测、对象级灾损、人口暴露、路网绕行和空间资源匹配纳入同一 MapGIS 桌面工作台。</p>")
                .append("<h2>系统架构与技术路线</h2><p>Java + MapGIS SDK 承担地图显示、原生空间叠加、专题图和路网分析；FastAPI/PyTorch 提供遥感检测服务。数据经灾损分析、风险评估、道路影响、路线与资源匹配形成证据链。</p>")
                .append("<h2>AI 模型与 MapGIS 二次开发</h2><p>本次 AI 步骤为")
                .append(ai.path("mode").asText().equals("REPLAY")?"对象预测结果回放；未声称当次实时推理。":"实时推理；模型精度仍需独立核验。")
                .append(" MapGIS 原生要素类、GeometryOperator、NetCls/NetAnalyse 与 MapControl 用于 GIS 计算及展示。</p>")
                .append("<h2>创新点</h2><p>逐阶段持久化来源证据；缺失真实洪水面或资源风险字段时停止综合评估；封路状态映射至原生路网并对比绕行路线。</p>")
                .append("<h2>一、灾害概况</h2><p>MapGIS 计算的洪水面面积：")
                .append(fmt(evidence.floodAreaSquareMetres()/1_000_000)).append(" km²。</p>")
                .append("<h2>二、AI 检测结果</h2><p>证据来源：").append(esc(ai.path("source").asText())).append("；状态：")
                .append(esc(ai.path("status").asText())).append("。</p>");
        image(html,imageNames,"flood","洪水专题地图");
        html.append("<h2>三、灾损统计</h2><table><tr><th>类别</th><th>对象数</th></tr>");
        damage.path("counts").fields().forEachRemaining(item->html.append("<tr><td>").append(esc(item.getKey())).append("</td><td>")
                .append(esc(item.getValue().asText())).append("</td></tr>"));
        html.append("</table>"); image(html,imageNames,"damage","建筑道路灾损专题图");
        html.append("<h2>四、风险评估</h2><table><tr><th>区域</th><th>等级</th><th>指数</th><th>影响人口</th></tr>");
        for (JsonNode area:risk.path("areas")) html.append("<tr><td>").append(esc(area.path("area").asText()))
                .append("</td><td>").append(esc(area.path("riskLevel").asText()))
                .append("</td><td>").append(esc(area.path("riskScore").asText()))
                .append("</td><td>").append(esc(area.path("affectedPopulation").asText())).append("</td></tr>");
        html.append("</table>"); image(html,imageNames,"risk","风险分区地图");
        html.append("<h2>五、道路影响分析</h2><p>阻断道路避让数：")
                .append(route.path("blocked_roads_removed").asInt()).append("；危险道路避让数：")
                .append(route.path("dangerous_roads_avoided").asInt()).append("。</p>");
        image(html,imageNames,"closure","道路封闭模拟");
        html.append("<h2>六、救援路线</h2><table><tr><th>起点</th><th>目标</th><th>距离 m</th><th>预计时间 min</th><th>风险</th></tr><tr><td>")
                .append(esc(route.path("start").asText())).append("</td><td>").append(esc(route.path("target").asText()))
                .append("</td><td>").append(esc(route.path("distance").asText())).append("</td><td>")
                .append(esc(route.path("time").asText())).append("</td><td>")
                .append(esc(route.path("risk_level").asText())).append("</td></tr></table>");
        image(html,imageNames,"route","封路前后路线对比");
        html.append("<h2>七、资源调度方案</h2><ul>");
        for (JsonNode recommendation:resources.path("recommendations"))
            html.append("<li>").append(esc(recommendation.asText())).append("</li>");
        html.append("</ul>"); image(html,imageNames,"resources","MapGIS 资源分布图");
        html.append("<h2>实验结果与验收边界</h2><p>本报告展示本次案例的灾损对象、风险指数、路线距离与资源推荐。模拟演练结果不等于现场灾情；模型精度、地图渲染和空间计算须结合对应运行日志及截图核查。</p>");
        html.append("<p>路线时间以演练速度估算；实际救援须核对路况、资源状态和现场安全。</p></body></html>");
        Path report=directory.resolve("FloodGuard_Final_Report.html");
        Files.writeString(report,html.toString(),StandardOpenOption.CREATE_NEW);
        return report;
    }
    private JsonNode read(Path file) throws Exception {
        if (file==null || !Files.isRegularFile(file) || Files.size(file)>16_000_000) throw new IllegalArgumentException("报告阶段证据缺失或过大："+file);
        return json.readTree(file.toFile());
    }
    private static void image(StringBuilder html,Map<String,String> images,String key,String caption) {
        String path=images.get(key);
        if (path!=null) html.append("<figure><img src='").append(esc(path)).append("' alt='")
                .append(esc(caption)).append("'><figcaption>").append(esc(caption)).append("</figcaption></figure>");
        else html.append("<p>阶段截图尚未采集：").append(esc(caption)).append("。</p>");
    }
    private static String fmt(double number) { return String.format(Locale.ROOT,"%.3f",number); }
    private static String esc(String value) { return value.replace("&","&amp;").replace("<","&lt;")
            .replace(">","&gt;").replace("\"","&quot;").replace("'","&#39;"); }
}
