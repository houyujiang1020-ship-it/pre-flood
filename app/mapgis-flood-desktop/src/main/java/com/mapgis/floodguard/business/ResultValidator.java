package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.util.*;

/** Cross-checks persisted MapGIS outputs without pretending to independently re-run GIS. */
public final class ResultValidator {
    private final ObjectMapper json=new ObjectMapper();
    public static void main(String[] args) throws Exception {
        if (args.length!=4) throw new IllegalArgumentException("damage manifest, risk report, route report, output JSON required");
        System.out.println(new ResultValidator().validate(Path.of(args[0]),Path.of(args[1]),Path.of(args[2]),
                Path.of(args[3])).toAbsolutePath());
    }
    public Path validate(Path damageFile,Path riskFile,Path routeFile,Path output) throws Exception {
        Map<String,Object> checks=new LinkedHashMap<>(), metrics=new LinkedHashMap<>();
        JsonNode damage=read(damageFile), risk=read(riskFile), route=read(routeFile);
        checks.put("damage_evidence",damage==null?"MISSING":
                "native_mapgis_layers_loaded".equals(damage.path("status").asText())?"PASS":"FAIL");
        checks.put("risk_evidence",risk==null?"MISSING":
                "MapGIS".equals(risk.path("engine").asText()) && "COMPLETE".equals(risk.path("status").asText())?"PASS":"FAIL");
        checks.put("route_evidence",route==null?"MISSING":
                route.path("network_url").asText().startsWith("gdbp://") && route.path("optimized").isObject()?"PASS":"FAIL");
        if (damage!=null && damage.path("counts").isObject()) {
            JsonNode counts=damage.path("counts");
            int normal=count(counts,"BUILDING_NORMAL"),flooded=count(counts,"BUILDING_FLOODED");
            int normalRoads=count(counts,"ROAD_NORMAL"),blockedRoads=count(counts,"ROAD_BLOCKED");
            metrics.put("building_total",normal+flooded); metrics.put("building_flooded",flooded);
            metrics.put("road_normal_objects",normalRoads); metrics.put("road_blocked_objects",blockedRoads);
            checks.put("building_counts",normal>=0 && flooded>=0 && normalRoads>=0 && blockedRoads>=0
                    && flooded<=normal+flooded?"PASS":"FAIL");
        } else checks.put("building_counts","MISSING");
        if (risk!=null && risk.path("areas").isArray() && !risk.path("areas").isEmpty()) {
            List<Map<String,Object>> areas=new ArrayList<>(); boolean allValid=true;
            for (JsonNode area:risk.path("areas")) {
                int total=area.path("totalBuildings").asInt(-1), flooded=area.path("damagedBuildings").asInt(-1);
                int blockedRoadCount=area.path("blockedRoads").asInt(-1);
                double roads=number(area,"totalRoadMetres"),blocked=number(area,"blockedRoadMetres");
                double population=number(area,"totalPopulation"),affected=number(area,"affectedPopulation");
                double br=number(area,"buildingRisk"),pr=number(area,"populationRisk"),rr=number(area,"roadRisk");
                double resource=number(area,"resourceDistanceRisk"),score=number(area,"riskScore");
                double expected=.4*br+.3*pr+.2*rr+.1*resource;
                boolean valid=total>0 && flooded>=0 && flooded<=total && blockedRoadCount>=0
                        && roads>0 && blocked>=0 && blocked<=roads+1e-6
                        && population>0 && affected>=0 && affected<=population+1e-6
                        && close(br,(double)flooded/total) && close(pr,affected/population)
                        && close(rr,blocked/roads) && close(score,expected) && score>=0 && score<=1;
                allValid &= valid;
                areas.add(Map.of("area",area.path("area").asText(),"building_total",total,
                        "building_flooded",flooded,"road_total_m",roads,"road_blocked_m",blocked,
                        "population_total",population,"population_affected",affected,
                        "risk_score",score,"blocked_roads",blockedRoadCount,"consistent",valid));
            }
            metrics.put("areas",areas); checks.put("risk_arithmetic",allValid?"PASS":"FAIL");
        } else checks.put("risk_arithmetic","MISSING");
        if (route!=null) {
            double distance=number(route,"distance"), optimized=number(route.path("optimized"),"distanceMetres");
            int roads=route.path("road_count").asInt(-1);
            JsonNode edges=route.path("optimized").path("edges");
            metrics.put("route_distance_m",distance); metrics.put("route_road_count",roads);
            checks.put("route_arithmetic",distance>=0 && close(distance,optimized) && edges.isArray()
                    && roads==edges.size()?"PASS":"FAIL");
        } else checks.put("route_arithmetic","MISSING");
        checks.put("independent_spatial_recheck","NOT_PERFORMED");
        boolean consistent=checks.values().stream().filter("PASS"::equals).count()>=6
                && checks.values().stream().noneMatch(v->"FAIL".equals(v)||"MISSING".equals(v));
        Map<String,Object> report=new LinkedHashMap<>(); report.put("schema_version",1);
        report.put("cross_evidence_consistent",consistent); report.put("final_acceptance","NOT_VERIFIED");
        report.put("checks",checks); report.put("metrics",metrics);
        report.put("inputs",Map.of("damage",String.valueOf(damageFile),"risk",String.valueOf(riskFile),"route",String.valueOf(routeFile)));
        Files.createDirectories(output.toAbsolutePath().normalize().getParent());
        Files.writeString(output,json.writerWithDefaultPrettyPrinter().writeValueAsString(report),
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);
        return output;
    }
    private JsonNode read(Path file) throws Exception {
        if (file==null || !Files.isRegularFile(file)) return null;
        if (Files.size(file)>16_000_000) throw new IllegalArgumentException("结果文件过大："+file);
        return json.readTree(file.toFile());
    }
    private static int count(JsonNode counts,String field) {
        JsonNode value=counts.path(field); return value.isIntegralNumber()?value.asInt():-1;
    }
    private static double number(JsonNode object,String field) {
        JsonNode value=object.path(field); return value.isNumber()?value.asDouble():Double.NaN;
    }
    private static boolean close(double a,double b) {
        return Double.isFinite(a) && Double.isFinite(b) && Math.abs(a-b)<=1e-5*Math.max(1,Math.max(Math.abs(a),Math.abs(b)));
    }
}
