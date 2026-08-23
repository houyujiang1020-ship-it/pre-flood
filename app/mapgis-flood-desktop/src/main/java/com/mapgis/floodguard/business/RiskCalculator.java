package com.mapgis.floodguard.business;

import java.util.Map;

public final class RiskCalculator {
    public record Weights(double flood, double population, double buildingDamage,
                          double roadAccessibility, double medicalAccessibility) {
        public Weights {
            double sum = flood + population + buildingDamage + roadAccessibility + medicalAccessibility;
            if (Math.abs(sum - 1.0) > 1.0e-9) throw new IllegalArgumentException("Risk weights must sum to 1.0");
        }
        public static Weights defaults() { return new Weights(0.30, 0.25, 0.20, 0.15, 0.10); }
    }

    public enum Level { LOW, MEDIUM, HIGH, EXTREME }

    private final Weights weights;

    public RiskCalculator(Weights weights) { this.weights = weights; }

    public double score(Map<String, Double> indicators) {
        double score = weights.flood * value(indicators, "flood")
                + weights.population * value(indicators, "population")
                + weights.buildingDamage * value(indicators, "buildingDamage")
                + weights.roadAccessibility * value(indicators, "roadAccessibility")
                + weights.medicalAccessibility * value(indicators, "medicalAccessibility");
        return Math.max(0.0, Math.min(1.0, score));
    }

    public Level level(double score) {
        if (score < 0.25) return Level.LOW;
        if (score < 0.50) return Level.MEDIUM;
        if (score < 0.75) return Level.HIGH;
        return Level.EXTREME;
    }

    private static double value(Map<String, Double> indicators, String name) {
        double value = indicators.getOrDefault(name, 0.0);
        if (value < 0 || value > 1) throw new IllegalArgumentException(name + " must be between 0 and 1");
        return value;
    }
}
