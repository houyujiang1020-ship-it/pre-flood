package com.mapgis.floodguard.business;

public record RoadEdge(String id, String from, String to, double distanceKm, double speedKph, FloodLevel floodLevel) {
    public enum FloodLevel { NORMAL, LIGHT, SEVERE, IMPASSABLE }

    public boolean passable() { return floodLevel != FloodLevel.IMPASSABLE; }

    public double travelMinutes() {
        if (!passable()) return Double.POSITIVE_INFINITY;
        double penalty = switch (floodLevel) { case NORMAL -> 1.0; case LIGHT -> 1.5; case SEVERE -> 4.0; case IMPASSABLE -> Double.POSITIVE_INFINITY; };
        return distanceKm / speedKph * 60.0 * penalty;
    }
}
