package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.FloodRiskScore;
import com.mapgis.floodguard.business.RiskDecision;
import com.mapgis.floodguard.business.RiskSpatialRules;
import com.mapgis.floodguard.business.RoadRiskEvidence;
import com.zondy.mapgis.att.Record;
import com.zondy.mapgis.geodatabase.*;
import com.zondy.mapgis.geometry.*;
import com.zondy.mapgis.map.VectorLayer;
import com.zondy.mapgis.srs.SRefData;
import java.nio.file.*;
import java.util.*;

/** Native MapGIS overlays and measurements for administrative flood risk. */
public final class FloodRiskAssessment {
    public record Inputs(VectorLayer areas, VectorLayer populationGrid, VectorLayer floodExtent,
                         VectorLayer buildingsNormal, VectorLayer buildingsFlooded,
                         VectorLayer roadsNormal, VectorLayer roadsAffected, VectorLayer roadsBlocked,
                         VectorLayer originalRoads,
                         String areaNameField, String resourceRiskField,
                         Path roadStatusLedger, String originalRoadsUrl, String caseMode) {
        public Inputs(VectorLayer areas, VectorLayer populationGrid, VectorLayer floodExtent,
                      VectorLayer buildingsNormal, VectorLayer buildingsFlooded,
                      VectorLayer roadsNormal, VectorLayer roadsAffected, VectorLayer roadsBlocked,
                      String areaNameField, String resourceRiskField) {
            this(areas,populationGrid,floodExtent,buildingsNormal,buildingsFlooded,
                    roadsNormal,roadsAffected,roadsBlocked,null,areaNameField,resourceRiskField,null,null,"UNSPECIFIED");
        }
    }
    public record AreaResult(String areaId, String area, int totalBuildings, int damagedBuildings,
                             Double buildingRisk, Double totalPopulation, Double affectedPopulation,
                             Double populationRisk, double totalRoadMetres, double blockedRoadMetres,
                             int blockedRoads, Double roadRisk, Double resourceDistanceRisk,
                             Double riskScore, String riskLevel, String status, String reason,
                             RiskDecision.Result evidence) {}
    public record Result(Path directory, Path reportJson, Path reportHtml, List<AreaResult> areas) {}
    private record Feature(Geometry geometry, java.util.Map<String,Object> fields) {}
    private static final ObjectMapper JSON = new ObjectMapper();

    public Result assess(Inputs input, Path output) throws Exception {
        Objects.requireNonNull(input);
        for (VectorLayer layer : Arrays.asList(input.areas(),input.buildingsNormal(),input.buildingsFlooded(),
                input.roadsNormal(),input.roadsBlocked()))
            requireLayer(layer);
        if (input.populationGrid()!=null) requireLayer(input.populationGrid());
        if (input.floodExtent()!=null) requireLayer(input.floodExtent());
        if (input.roadsAffected()!=null) requireLayer(input.roadsAffected());
        if (input.originalRoads()!=null) requireLayer(input.originalRoads());
        if (input.areaNameField()==null || input.areaNameField().isBlank()
                || input.resourceRiskField()==null || input.resourceRiskField().isBlank())
            throw new IllegalArgumentException("必须指定行政区名称及 MapGIS 资源距离风险字段");
        SRefData target = input.areas().getSrefInfo();
        if (target==null || !isMetreProjection(target.toWkt()))
            throw new IllegalArgumentException("行政区图层必须为米制投影");
        java.util.Map<String,String> references=new LinkedHashMap<>();
        VectorLayer[] spatialLayers={input.areas(),input.populationGrid(),input.floodExtent(),input.buildingsNormal(),
                input.buildingsFlooded(),input.roadsNormal(),input.roadsAffected(),input.roadsBlocked(),input.originalRoads()};
        String[] roles={"areas","population","flood_extent","buildings_normal","buildings_flooded",
                "roads_normal","roads_affected","roads_blocked","roads_original"};
        for (int i=0;i<roles.length;i++) if (spatialLayers[i]!=null)
            references.put(roles[i],spatialLayers[i].getSrefInfo().toWkt());
        RiskSpatialRules.requireSameCrs(target.toWkt(),references);
        Path directory = Files.createDirectories(output).resolve("risk-"+UUID.randomUUID());
        Files.createDirectory(directory);
        List<Feature> areas = List.of(), cells = List.of(), extent = List.of(), normalBuildings = List.of();
        List<Feature> floodedBuildings = List.of(), normalRoads = List.of(), affectedRoads = List.of(), blockedRoads = List.of(), originalRoads = List.of();
        try {
            areas = read(input.areas(),target,10_000);
            cells = input.populationGrid()==null ? List.of() : read(input.populationGrid(),target,200_000);
            extent = input.floodExtent()==null ? List.of() : read(input.floodExtent(),target,50_000);
            normalBuildings = read(input.buildingsNormal(),target,200_000);
            floodedBuildings = read(input.buildingsFlooded(),target,200_000);
            normalRoads = read(input.roadsNormal(),target,200_000);
            affectedRoads = input.roadsAffected()==null ? List.of() : read(input.roadsAffected(),target,200_000);
            blockedRoads = read(input.roadsBlocked(),target,200_000);
            originalRoads = input.originalRoads()==null ? List.of() : read(input.originalRoads(),target,200_000);
            if (areas.isEmpty()) throw new IllegalArgumentException("行政区图层必须包含有效对象");
            validateAreas(areas);
            validateObjects(normalBuildings,floodedBuildings,normalRoads,affectedRoads,blockedRoads);
            validateCells(cells);
            validateFloodExtent(extent);
            RoadRiskEvidence.Verified roadEvidence=null;
            String roadEvidenceIssue="原始道路图层或道路状态核查单未绑定";
            try {
                if (input.originalRoads()==null || originalRoads.isEmpty()
                        || !input.originalRoads().getURL().equals(input.originalRoadsUrl()))
                    throw new IllegalArgumentException("原始道路图层与案例 URL 不一致或为空");
                Set<String> allRoadIds=new HashSet<>(), classifiedIds=new HashSet<>(), blockedIds=new HashSet<>();
                for (Feature road:originalRoads) {
                    String id=string(road,"object_id"); RiskSpatialRules.requireUnique(id,"原始道路",allRoadIds);
                    if (!(road.geometry() instanceof GeoLine) || length(road.geometry())<=0)
                        throw new IllegalArgumentException("原始道路几何无效："+id);
                }
                for (Feature road:normalRoads) classifiedIds.add(string(road,"object_id"));
                for (Feature road:affectedRoads) classifiedIds.add(string(road,"object_id"));
                for (Feature road:blockedRoads) {
                    String id=string(road,"object_id"); classifiedIds.add(id); blockedIds.add(id);
                }
                if (!classifiedIds.equals(allRoadIds))
                    throw new IllegalArgumentException("分类道路与原始道路对象 ID 库存不一致");
                roadEvidence=RoadRiskEvidence.verify(input.roadStatusLedger(),input.originalRoadsUrl(),allRoadIds,blockedIds);
                roadEvidenceIssue="";
            } catch (Exception evidenceError) { roadEvidenceIssue=evidenceError.getMessage(); }
            java.util.Map<String,Integer> normalByArea=assignBuildings(normalBuildings,areas);
            java.util.Map<String,Integer> floodedByArea=assignBuildings(floodedBuildings,areas);
            boolean populationReady = !cells.isEmpty() && !extent.isEmpty();
            List<AreaResult> results = new ArrayList<>();
            Set<String> names = new HashSet<>();
            for (Feature area : areas) {
                String areaId=string(area,"area_id");
                String name = string(area,input.areaNameField());
                if (name.isBlank() || !names.add(name)) throw new IllegalArgumentException("行政区名称缺失或重复："+name);
                int normalCount = normalByArea.getOrDefault(areaId,0);
                int floodedCount = floodedByArea.getOrDefault(areaId,0);
                double totalPop = 0, affectedPop = 0;
                Geometry coveredCells=null;
                try {
                for (Feature cell : cells) {
                    double pop = number(cell,"population");
                    double cellArea = area(cell.geometry());
                    Geometry withinArea = intersect(cell.geometry(),area.geometry());
                    if (withinArea==null) continue;
                    try {
                        double overlap = area(withinArea);
                        if (overlap<=0) continue;
                        if (coveredCells!=null) {
                            Geometry duplicate=intersect(coveredCells,withinArea);
                            try { if (duplicate!=null && area(duplicate)>1e-6)
                                throw new IllegalArgumentException("人口格网在行政区内重叠："+areaId); }
                            finally { if (duplicate!=null) duplicate.dispose(); }
                            Geometry union=GeometryOperator.overlay(coveredCells,withinArea,GeometryOperator.OverlayType.UNION,0.001);
                            if (union==null) throw new IllegalStateException("MapGIS 人口格网合并失败");
                            coveredCells.dispose(); coveredCells=union;
                        } else coveredCells=withinArea.clone();
                        totalPop += RiskSpatialRules.allocatedPopulation(pop,string(cell,"population_unit"),cellArea,overlap,string(cell,"grid_id"));
                        Geometry inundated = null;
                        try {
                            for (Feature flood : extent) {
                                if (!polygon(flood.geometry())) throw new IllegalArgumentException("洪水影响范围必须为面");
                                Geometry part = intersect(withinArea,flood.geometry());
                                if (part==null) continue;
                                if (inundated==null) inundated=part;
                                else {
                                    Geometry merged = GeometryOperator.overlay(inundated,part,GeometryOperator.OverlayType.UNION,0.001);
                                    inundated.dispose(); part.dispose();
                                    if (merged==null) throw new IllegalStateException("MapGIS 洪水面去重合并失败");
                                    inundated=merged;
                                }
                            }
                            if (inundated!=null) affectedPop += RiskSpatialRules.allocatedPopulation(pop,
                                    string(cell,"population_unit"),cellArea,Math.min(overlap,area(inundated)),string(cell,"grid_id"));
                        } finally { if (inundated!=null) inundated.dispose(); }
                    } finally { withinArea.dispose(); }
                }
                } finally { if (coveredCells!=null) coveredCells.dispose(); }
                double normalLength = clippedLength(normalRoads,area.geometry());
                double affectedLength = clippedLength(affectedRoads,area.geometry());
                double blockedLength = clippedLength(blockedRoads,area.geometry());
                double allLength = normalLength+affectedLength+blockedLength;
                int blockedCount = countIntersecting(blockedRoads,area.geometry());
                Object resourceValue=area.fields().get(input.resourceRiskField());
                Double resourceRisk=resourceValue instanceof Number value?value.doubleValue():null;
                var buildingMetric=RiskDecision.ratio("building",(double)floodedCount,(double)(normalCount+floodedCount),
                        input.buildingsNormal().getURL()+" | "+input.buildingsFlooded().getURL());
                var populationMetric=populationReady
                        ? RiskDecision.ratio("population",affectedPop,totalPop,
                                input.populationGrid().getURL()+" | "+input.floodExtent().getURL())
                        : RiskDecision.missing("population",null,cells.isEmpty()?null:totalPop,
                                "缺少人口格网或独立连续洪水面",input.populationGrid()==null?null:input.populationGrid().getURL());
                var roadMetric=roadEvidence==null
                        ? RiskDecision.missing("road",blockedLength,allLength,roadEvidenceIssue,
                                input.roadsNormal().getURL()+" | "+input.roadsBlocked().getURL())
                        : RiskDecision.ratio("road",blockedLength,allLength,
                                roadEvidence.path()+"#"+roadEvidence.sha256());
                String resourceSource=string(area,"resource_risk_source");
                String resourceMethod=string(area,"resource_risk_method");
                var distanceMetric=RiskDecision.scalar("resource_distance",resourceRisk,
                        resourceSource.isBlank() || resourceMethod.isBlank()?null:
                        input.areas().getURL()+"#"+input.resourceRiskField()+" | "+resourceSource+" | "+resourceMethod);
                var decision=RiskDecision.evaluate(buildingMetric,populationMetric,roadMetric,distanceMetric);
                results.add(new AreaResult(areaId,name,normalCount+floodedCount,floodedCount,buildingMetric.value(),
                        cells.isEmpty()?null:totalPop,populationReady?affectedPop:null,populationMetric.value(),
                        allLength,blockedLength,blockedCount,roadMetric.value(),distanceMetric.value(),
                        decision.riskScore(),decision.riskLevel(),decision.status(),String.join("；",decision.reasons()),decision));
            }
            java.util.Map<String,Object> report = new LinkedHashMap<>();
            report.put("schema_version",1); report.put("engine","MapGIS");
            report.put("method","native same-CRS overlay; unique building owner by largest clipped area; nonoverlapping persons-per-cell area allocation; independent flood polygon");
            report.put("population_unit","persons_per_cell");
            report.put("spatial_validation","same projected-metre CRS; unique IDs; disjoint areas and population cells; no inferred road closures");
            report.put("weights",java.util.Map.of("building",.4,"population",.3,"road",.2,"resource_distance",.1));
            report.put("crs_wkt",target.toWkt()); report.put("areas",results);
            report.put("sources",sources(input));
            report.put("road_status_evidence",roadEvidence);
            report.put("road_status_issue",roadEvidenceIssue);
            report.put("calculated_at",java.time.Instant.now().toString());
            report.put("case_mode",input.caseMode());
            report.put("case_acceptance","UNVERIFIED");
            report.put("building_count_semantics","damagedBuildings legacy field means flooded buildings, not structural damage");
            report.put("status",results.stream().allMatch(a -> "COMPLETE".equals(a.status())) ? "COMPLETE" : "PARTIAL");
            report.put("field_verification",false); report.put("model_accuracy_verified",false);
            if (results.size()==1) {
                AreaResult one=results.get(0);
                report.put("area",one.area()); report.put("risk_level",one.riskLevel()); report.put("risk_score",one.riskScore());
                report.put("affected_population",one.affectedPopulation()); report.put("damaged_buildings",one.damagedBuildings());
                report.put("flooded_buildings",one.damagedBuildings());
                report.put("blocked_roads",one.blockedRoads());
            }
            Path reportJson=directory.resolve("risk_report.json");
            Files.writeString(reportJson,JSON.writerWithDefaultPrettyPrinter().writeValueAsString(report),StandardOpenOption.CREATE_NEW);
            Path reportHtml=directory.resolve("risk_report.html");
            Files.writeString(reportHtml,html(results),StandardOpenOption.CREATE_NEW);
            return new Result(directory,reportJson,reportHtml,List.copyOf(results));
        } finally {
            for (List<Feature> list : List.of(areas,cells,extent,normalBuildings,floodedBuildings,
                    normalRoads,affectedRoads,blockedRoads,originalRoads))
                for (Feature feature : list) feature.geometry().dispose();
        }
    }
    private static void requireLayer(VectorLayer layer) {
        if (layer==null || !(layer.getData() instanceof SFeatureCls features) || !features.hasOpened())
            throw new IllegalArgumentException("缺少已打开的 MapGIS 原生矢量图层");
        if (layer.getSrefInfo()==null) throw new IllegalArgumentException("图层缺少空间参考："+layer.getName());
        if (layer.getURL()==null || !layer.getURL().startsWith("gdbp://"))
            throw new IllegalArgumentException("风险输入必须为可追溯的 MapGIS gdbp 图层："+layer.getName());
    }
    private static boolean isMetreProjection(String wkt) {
        String lower=wkt.toLowerCase(Locale.ROOT);
        return lower.startsWith("projcs[") && (lower.contains("unit[\"metre\",1") || lower.contains("unit[\"meter\",1"));
    }
    private static List<Feature> read(VectorLayer layer,SRefData target,int limit) {
        SFeatureCls cls=(SFeatureCls)layer.getData();
        QueryDef query=new QueryDef(); RecordSet rows=null;
        List<Feature> out=new ArrayList<>();
        try {
            rows=cls.query(query);
            if (rows==null) throw new IllegalStateException("MapGIS 查询失败："+layer.getName());
            int count=rows.getCount();
            if (count<0 || count>limit) throw new IllegalArgumentException("图层对象数超出交互限制："+layer.getName());
            if (count>0) rows.moveFirst();
            for (int i=0;i<count;i++) {
                Geometry geometry=rows.getGeometry(); Record attributes=rows.getAtt();
                if (geometry==null || attributes==null) throw new IllegalStateException("缺少几何或属性："+layer.getName());
                try {
                    Geometry projected;
                    if (layer.getSrefInfo().toWkt().equals(target.toWkt())) projected=geometry.clone();
                    else projected=GeometryOperator.project(geometry,layer.getSrefInfo(),target);
                    if (projected==null || projected.isEmpty()) throw new IllegalStateException("MapGIS 投影失败："+layer.getName());
                    java.util.Map<String,Object> fields=new HashMap<>();
                    var schema=attributes.getFields();
                    try {
                        for (short f=0;f<schema.getFieldCount();f++) {
                            var field=schema.getField(f);
                            try { fields.put(field.getFieldName(),attributes.getFieldVal(f)); }
                            finally { field.dispose(); }
                        }
                    } finally { schema.dispose(); }
                    out.add(new Feature(projected,fields));
                } finally { geometry.dispose(); attributes.dispose(); }
                if (i+1<count) rows.moveNext();
            }
            return out;
        } catch (RuntimeException | Error error) {
            for (Feature feature : out) feature.geometry().dispose();
            throw error;
        } finally { if (rows!=null) rows.dispose(); query.dispose(); }
    }
    private static String string(Feature feature,String name) {
        Object value=feature.fields().get(name);
        return value==null ? "" : value.toString().trim();
    }
    private static double number(Feature feature,String name) {
        Object value=feature.fields().get(name);
        if (!(value instanceof Number number) || !Double.isFinite(number.doubleValue()))
            throw new IllegalArgumentException("缺少数值字段 " + name);
        return number.doubleValue();
    }
    private static void validateAreas(List<Feature> areas) {
        Set<String> ids=new HashSet<>();
        for (int i=0;i<areas.size();i++) {
            Feature current=areas.get(i);
            RiskSpatialRules.requireUnique(string(current,"area_id"),"行政区",ids);
            if (!polygon(current.geometry()) || area(current.geometry())<=0)
                throw new IllegalArgumentException("行政区几何无效："+string(current,"area_id"));
            for (int j=0;j<i;j++) {
                Geometry overlap=intersect(current.geometry(),areas.get(j).geometry());
                try { if (overlap!=null && area(overlap)>1e-6)
                    throw new IllegalArgumentException("行政区面重叠："+string(current,"area_id")); }
                finally { if (overlap!=null) overlap.dispose(); }
            }
        }
    }
    private static void validateCells(List<Feature> cells) {
        Set<String> ids=new HashSet<>();
        for (Feature cell:cells) {
            String id=string(cell,"grid_id");
            RiskSpatialRules.requireUnique(id,"人口格网",ids);
            if (!polygon(cell.geometry()) || area(cell.geometry())<=0)
                throw new IllegalArgumentException("人口格网几何无效："+id);
            RiskSpatialRules.allocatedPopulation(number(cell,"population"),string(cell,"population_unit"),
                    area(cell.geometry()),0,id);
            if (string(cell,"population_source").isBlank())
                throw new IllegalArgumentException("人口格网来源缺失："+id);
        }
    }
    private static void validateFloodExtent(List<Feature> extent) {
        for (Feature flood:extent) {
            if (!polygon(flood.geometry()) || area(flood.geometry())<=0)
                throw new IllegalArgumentException("连续洪水面几何无效");
            if (!"CONTINUOUS_EXTENT".equals(string(flood,"flood_kind"))
                    || string(flood,"flood_source").isBlank())
                throw new IllegalArgumentException("洪水面缺少独立连续范围及来源证据，不能使用受淹对象掩膜");
        }
    }
    @SafeVarargs private static void validateObjects(List<Feature> normalBuildings,List<Feature> floodedBuildings,
                                                       List<Feature>... roadGroups) {
        Set<String> buildingIds=new HashSet<>(), roadIds=new HashSet<>();
        for (Feature feature:normalBuildings) validateObject(feature,"建筑",buildingIds,true);
        for (Feature feature:floodedBuildings) validateObject(feature,"建筑",buildingIds,true);
        for (List<Feature> group:roadGroups)
            for (Feature feature:group) validateObject(feature,"道路",roadIds,false);
    }
    private static void validateObject(Feature feature,String role,Set<String> ids,boolean building) {
        String id=string(feature,"object_id");
        RiskSpatialRules.requireUnique(id,role,ids);
        if (building ? !polygon(feature.geometry()) || area(feature.geometry())<=0
                     : !(feature.geometry() instanceof GeoLine) || length(feature.geometry())<=0)
            throw new IllegalArgumentException(role+"几何无效："+id);
    }
    private static java.util.Map<String,Integer> assignBuildings(List<Feature> buildings,List<Feature> areas) {
        java.util.Map<String,Integer> counts=new HashMap<>();
        for (Feature building:buildings) {
            java.util.Map<String,Double> intersections=new LinkedHashMap<>();
            for (Feature zone:areas) {
                Geometry clipped=intersect(building.geometry(),zone.geometry());
                try { intersections.put(string(zone,"area_id"),clipped==null?0:area(clipped)); }
                finally { if (clipped!=null) clipped.dispose(); }
            }
            String owner=RiskSpatialRules.owner(intersections,string(building,"object_id"));
            if (owner!=null) counts.merge(owner,1,Integer::sum);
        }
        return counts;
    }
    private static boolean polygon(Geometry g) { return g instanceof GeoPolygon || g instanceof GeoMultiPolygon; }
    private static double area(Geometry geometry) {
        double result=GeometryOperator.calculateArea(geometry);
        if (!Double.isFinite(result) || result<0) throw new IllegalStateException("MapGIS 面积计算失败");
        return result;
    }
    private static Geometry intersect(Geometry first,Geometry second) {
        Geometry intersection=GeometryOperator.overlay(first,second,GeometryOperator.OverlayType.INTER,0.001);
        if (intersection!=null && intersection.isEmpty()) { intersection.dispose(); return null; }
        return intersection;
    }
    private static int countIntersecting(List<Feature> features,Geometry area) {
        int count=0;
        for (Feature feature : features) {
            Geometry clipped=intersect(feature.geometry(),area);
            if (clipped!=null) {
                try { if (polygon(clipped) ? area(clipped)>0 : length(clipped)>0) count++; }
                finally { clipped.dispose(); }
            }
        }
        return count;
    }
    private static double clippedLength(List<Feature> roads,Geometry area) {
        double length=0;
        for (Feature road : roads) {
            Geometry clipped=intersect(road.geometry(),area);
            if (clipped!=null) { try { length+=length(clipped); } finally { clipped.dispose(); } }
        }
        return length;
    }
    private static double length(Geometry geometry) {
        double length=GeometryOperator.calculateLineLength(geometry);
        if (!Double.isFinite(length) || length<0) throw new IllegalStateException("MapGIS 道路长度计算失败");
        return length;
    }
    private static java.util.Map<String,Object> sources(Inputs i) {
        java.util.Map<String,Object> out=new LinkedHashMap<>();
        out.put("areas",i.areas().getURL()); out.put("population",i.populationGrid()==null?null:i.populationGrid().getURL());
        out.put("flood_extent",i.floodExtent()==null?null:i.floodExtent().getURL()); out.put("buildings_normal",i.buildingsNormal().getURL());
        out.put("buildings_flooded",i.buildingsFlooded().getURL()); out.put("roads_normal",i.roadsNormal().getURL());
        out.put("roads_blocked",i.roadsBlocked().getURL());
        if (i.roadsAffected()!=null) out.put("roads_affected",i.roadsAffected().getURL());
        out.put("area_name_field",i.areaNameField()); out.put("resource_risk_field",i.resourceRiskField());
        out.put("road_status_ledger",i.roadStatusLedger()==null?null:i.roadStatusLedger().toString());
        out.put("original_roads",i.originalRoadsUrl());
        return out;
    }
    private static String html(List<AreaResult> areas) {
        StringBuilder text=new StringBuilder("<!doctype html><meta charset='utf-8'><title>FloodGuard 风险报告</title>")
                .append("<h1>MapGIS 洪涝风险评估</h1><p>风险需真实洪水面、人口格网和资源距离证据；未完成现场核验。</p>")
                .append("<table border='1' cellspacing='0' cellpadding='6'><tr><th>区域 ID</th><th>区域</th><th>等级</th><th>综合指数</th><th>建筑风险</th><th>人口风险</th><th>道路风险</th><th>资源距离风险</th><th>建筑</th><th>受淹建筑</th><th>总人口</th><th>影响人口</th><th>道路总长 m</th><th>阻断 m</th><th>状态</th></tr>");
        for (AreaResult a:areas) text.append("<tr><td>").append(escape(a.areaId())).append("</td><td>").append(escape(a.area())).append("</td><td>")
                .append(a.riskLevel()==null?"—":a.riskLevel()).append("</td><td>")
                .append(a.riskScore()==null?"—":String.format(Locale.ROOT,"%.4f",a.riskScore())).append("</td><td>")
                .append(format(a.buildingRisk())).append("</td><td>").append(format(a.populationRisk())).append("</td><td>")
                .append(format(a.roadRisk())).append("</td><td>").append(format(a.resourceDistanceRisk())).append("</td><td>")
                .append(a.totalBuildings()).append("</td><td>").append(a.damagedBuildings()).append("</td><td>")
                .append(a.totalPopulation()==null?"—":String.format(Locale.ROOT,"%.2f",a.totalPopulation())).append("</td><td>")
                .append(a.affectedPopulation()==null?"—":String.format(Locale.ROOT,"%.2f",a.affectedPopulation())).append("</td><td>")
                .append(String.format(Locale.ROOT,"%.2f",a.totalRoadMetres())).append("</td><td>")
                .append(String.format(Locale.ROOT,"%.2f",a.blockedRoadMetres())).append("</td><td>")
                .append(escape(a.status())).append(a.reason().isBlank()?"":"："+escape(a.reason())).append("</td></tr>");
        return text.append("</table>").toString();
    }
    private static String format(Double value) { return value==null?"—":String.format(Locale.ROOT,"%.4f",value); }
    private static String escape(String value) { return value.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\"","&quot;"); }
}
