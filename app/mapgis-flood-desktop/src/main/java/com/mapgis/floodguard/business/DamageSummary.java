package com.mapgis.floodguard.business;

public record DamageSummary(double floodedAreaKm2, long floodedBuildings, long floodedRoads,
                            long blockedRoads, long affectedCommunities, long affectedPopulation) {
    public DamageSummary {
        if (floodedAreaKm2 < 0 || floodedBuildings < 0 || floodedRoads < 0 || blockedRoads < 0
                || affectedCommunities < 0 || affectedPopulation < 0) throw new IllegalArgumentException("Damage values cannot be negative");
    }
}
