package com.mapgis.floodguard.business;
import com.fasterxml.jackson.databind.JsonNode;

/** Reject wrong-grid/native pixel-space output rather than labeling it georeferenced. */
public final class GeoJsonPatchValidator {
    public static void validate(JsonNode geometry, RasterGrid grid) {
        if (!"Polygon".equals(geometry.path("type").asText())) throw new IllegalArgumentException("MapGIS未返回Polygon几何");
        JsonNode rings = geometry.path("coordinates");
        if (!rings.isArray() || rings.isEmpty()) throw new IllegalArgumentException("矢量区缺少坐标");
        double tolerance = Math.max(grid.dx(), -grid.dy()) * 1e-5;
        for (JsonNode ring : rings) {
            if (!ring.isArray() || ring.size() < 4 || !ring.get(0).equals(ring.get(ring.size()-1)))
                throw new IllegalArgumentException("矢量区环未闭合");
            for (JsonNode point : ring) {
                if (!point.isArray() || point.size() < 2 || !point.get(0).isNumber() || !point.get(1).isNumber())
                    throw new IllegalArgumentException("矢量坐标格式错误");
                double x = point.get(0).asDouble(), y = point.get(1).asDouble();
                if (!Double.isFinite(x) || !Double.isFinite(y) || x < grid.x()-tolerance
                        || x > grid.x()+grid.width()*grid.dx()+tolerance || y > grid.y()+tolerance
                        || y < grid.y()+grid.height()*grid.dy()-tolerance)
                    throw new IllegalArgumentException("矢量坐标超出源栅格范围，拒绝导出");
            }
        }
    }
}
