package com.mapgis.floodguard.business;

import java.util.*;

/** Four-factor decision with explicit evidence and no missing-value substitution. */
public final class RiskDecision {
    public record Metric(String name, Double numerator, Double denominator, Double value,
                         String source, String status, String reason) {}
    public record Result(Map<String,Metric> indicators, Double riskScore, String riskLevel,
                         String status, List<String> reasons) {}
    private RiskDecision() {}

    public static Metric ratio(String name, Double numerator, Double denominator, String source) {
        if (source==null || source.isBlank()) return new Metric(name,numerator,denominator,null,source,"MISSING","数据来源缺失");
        if (numerator==null || denominator==null) return missing(name,"分子或分母缺失",source);
        if (!Double.isFinite(numerator) || !Double.isFinite(denominator) || numerator<0 || denominator<0)
            return invalid(name,numerator,denominator,source,"分子或分母无效");
        if (denominator==0) return missing(name,"分母为零",source);
        if (numerator>denominator+1e-9) return invalid(name,numerator,denominator,source,"分子超过分母");
        return new Metric(name,numerator,denominator,Math.min(1,numerator/denominator),source,"VALID","");
    }
    public static Metric scalar(String name, Double value, String source) {
        if (source==null || source.isBlank()) return new Metric(name,value,1.0,null,source,"MISSING","数据来源缺失");
        if (value==null) return missing(name,"指标值缺失",source);
        if (!Double.isFinite(value) || value<0 || value>1)
            return invalid(name,value,1.0,source,"指标值不在 [0,1]");
        return new Metric(name,value,1.0,value,source,"VALID","");
    }
    public static Metric missing(String name,String reason,String source) {
        return new Metric(name,null,null,null,source,"MISSING",reason);
    }
    public static Metric missing(String name,Double numerator,Double denominator,String reason,String source) {
        return new Metric(name,numerator,denominator,null,source,"MISSING",reason);
    }
    private static Metric invalid(String name,Double numerator,Double denominator,String source,String reason) {
        return new Metric(name,numerator,denominator,null,source,"INVALID",reason);
    }
    public static Result evaluate(Metric building,Metric population,Metric road,Metric distance) {
        Map<String,Metric> metrics=new LinkedHashMap<>();
        for (Metric metric:List.of(building,population,road,distance)) {
            if (metric==null || metrics.putIfAbsent(metric.name(),metric)!=null)
                throw new IllegalArgumentException("风险指标缺失或重复");
        }
        if (!metrics.keySet().equals(Set.of("building","population","road","resource_distance")))
            throw new IllegalArgumentException("必须提供固定四项风险指标");
        List<String> reasons=metrics.values().stream().filter(m->!"VALID".equals(m.status()))
                .map(m->m.name()+"："+m.reason()).toList();
        if (!reasons.isEmpty())
            return new Result(Collections.unmodifiableMap(new LinkedHashMap<>(metrics)),null,null,"PARTIAL",reasons);
        FloodRiskScore.Result score=FloodRiskScore.calculate(building.value(),population.value(),road.value(),distance.value());
        return new Result(Collections.unmodifiableMap(new LinkedHashMap<>(metrics)),score.score(),score.level().name(),"COMPLETE",List.of());
    }
}
