package com.mapgis.floodguard.business;

import java.util.Map;

/** Unit and ownership rules shared by native MapGIS overlays and deterministic tests. */
public final class RiskSpatialRules {
    public static final String PERSONS_PER_CELL = "persons_per_cell";
    private RiskSpatialRules() {}

    public static void requireSameCrs(String areaWkt, Map<String,String> inputs) {
        if (areaWkt == null || areaWkt.isBlank()) throw new IllegalArgumentException("行政区缺少 CRS");
        for (var entry : inputs.entrySet()) {
            if (entry.getValue() == null || !areaWkt.trim().equals(entry.getValue().trim()))
                throw new IllegalArgumentException("空间参考不一致：" + entry.getKey());
        }
    }

    public static double allocatedPopulation(double persons, String unit, double cellArea,
                                             double clippedArea, String label) {
        if (!PERSONS_PER_CELL.equals(unit))
            throw new IllegalArgumentException(label + " 人口单位缺失或不是每格人数");
        if (!Double.isFinite(persons) || persons < 0 || !Double.isFinite(cellArea) || cellArea <= 0
                || !Double.isFinite(clippedArea) || clippedArea < 0 || clippedArea > cellArea + 1e-8)
            throw new IllegalArgumentException(label + " 人口或面积无效");
        return persons * Math.min(1, clippedArea / cellArea);
    }

    /** A building intersecting several zones belongs to its largest positive clipped area. Ties are ambiguous. */
    public static String owner(Map<String,Double> areaIntersections, String objectId) {
        if (objectId == null || objectId.isBlank()) throw new IllegalArgumentException("建筑 ID 缺失");
        String winner = null;
        double largest = 0;
        boolean tied = false;
        for (var entry : areaIntersections.entrySet()) {
            double area = entry.getValue();
            if (entry.getKey() == null || entry.getKey().isBlank() || !Double.isFinite(area) || area < 0)
                throw new IllegalArgumentException("建筑所属行政区面积无效：" + objectId);
            if (area > largest + 1e-8) { winner = entry.getKey(); largest = area; tied = false; }
            else if (area > 0 && Math.abs(area - largest) <= 1e-8) tied = true;
        }
        if (tied) throw new IllegalArgumentException("建筑跨行政区归属并列：" + objectId);
        return winner;
    }

    public static void requireUnique(String id, String role, java.util.Set<String> seen) {
        if (id == null || id.isBlank() || !seen.add(id))
            throw new IllegalArgumentException(role + " ID 缺失或重复：" + id);
    }
}
