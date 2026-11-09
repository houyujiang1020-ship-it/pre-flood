package com.mapgis.floodguard.business;

/** Scenario multipliers for native MapGIS network edge costs. */
public final class RoadImpedance {
    public enum Status { NORMAL, FLOODED, HIGH_RISK, BLOCKED }
    private RoadImpedance() {}
    public static int factor(Status status) {
        if (status == null) throw new IllegalArgumentException("Road status required");
        return switch (status) {
            case NORMAL -> 1;
            case FLOODED -> 10;
            case HIGH_RISK -> 50;
            case BLOCKED -> 999999;
        };
    }
    public static double costMetres(double lengthMetres,Status status) {
        if (!Double.isFinite(lengthMetres) || lengthMetres<=0) throw new IllegalArgumentException("Positive projected edge length required");
        return lengthMetres*factor(status);
    }
}
