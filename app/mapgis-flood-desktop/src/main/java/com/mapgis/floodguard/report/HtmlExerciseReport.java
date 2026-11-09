package com.mapgis.floodguard.report;

/** Diagnostic report, deliberately distinct from a real disaster/operational report. */
public final class HtmlExerciseReport {
    public String render(boolean passed,String evidence) {
        String escaped=evidence.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;");
        return "<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>演练路网联调验收</title>"
                +"<style>body{max-width:1100px;margin:40px auto;font:16px sans-serif;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f7;padding:20px}</style>"
                +"<h1>MapGIS 演练路网联调验收</h1><h2>"+(passed?"演练路径检查通过":"演练路径检查未通过")+"</h2>"
                +"<p>虚构演练资源；原生最短距离路径按假设匀速换算时间，不包含吸附接驳时间。不代表真实灾情、通行安全或实际调度指令。</p>"
                +"<p>正式命名分钟权业务调度仍未验收。请核对资源绑定距离、基线路径、封闭边及未满足需求。</p>"
                +"<p><a href='exercise-dispatch.json'>原始验收证据 JSON</a></p><pre>"+escaped+"</pre></html>";
    }
}
