package com.mapgis.floodguard.business;

/** Published four-factor risk formula; inputs are ratios already measured with MapGIS. */
public final class FloodRiskScore {
    public enum Level { LOW, MEDIUM, HIGH }
    public record Result(double buildingRisk, double populationRisk, double roadRisk,
                         double resourceDistanceRisk, double score, Level level) {}
    private FloodRiskScore() {}
    public static Result calculate(double buildingRisk, double populationRisk, double roadRisk,
                                   double resourceDistanceRisk) {
        check("buildingRisk",buildingRisk); check("populationRisk",populationRisk);
        check("roadRisk",roadRisk); check("resourceDistanceRisk",resourceDistanceRisk);
        double score = .4*buildingRisk + .3*populationRisk + .2*roadRisk + .1*resourceDistanceRisk;
        Level level = score < .3 ? Level.LOW : score < .6 ? Level.MEDIUM : Level.HIGH;
        return new Result(buildingRisk,populationRisk,roadRisk,resourceDistanceRisk,score,level);
    }
    public static double ratio(double numerator,double denominator,String label) {
        if (!Double.isFinite(numerator) || !Double.isFinite(denominator) || denominator<=0
                || numerator<0 || numerator>denominator+1e-9)
            throw new IllegalArgumentException(label+" 分子/分母无效；缺失不可记零");
        return Math.min(1,numerator/denominator);
    }
    private static void check(String label,double value) {
        if (!Double.isFinite(value) || value<0 || value>1)
            throw new IllegalArgumentException(label+" 必须在 [0,1]");
    }
}
