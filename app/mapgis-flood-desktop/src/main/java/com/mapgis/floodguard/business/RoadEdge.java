package com.mapgis.floodguard.business;

public record RoadEdge(String id, String from, String to, double distanceKm, double speedKph, FloodLevel floodLevel) {
    public RoadEdge {
        if (id == null || id.isBlank() || from == null || from.isBlank() || to == null || to.isBlank()
                || floodLevel == null || !Double.isFinite(distanceKm) || distanceKm < 0
                || !Double.isFinite(speedKph) || speedKph <= 0) {
            throw new IllegalArgumentException("Road requires identifiers, finite nonnegative distance and positive speed");
        }
    }
    public enum FloodLevel { NORMAL, LIGHT, SEVERE, IMPASSABLE }

    public boolean passable() { return floodLevel != FloodLevel.IMPASSABLE; }

    public double travelMinutes() {
        if (!passable()) return Double.POSITIVE_INFINITY;
        double penalty = switch (floodLevel) { case NORMAL -> 1.0; case LIGHT -> 1.5; case SEVERE -> 4.0; case IMPASSABLE -> Double.POSITIVE_INFINITY; };
        return distanceKm / speedKph * 60.0 * penalty;
    }
}
