package com.mapgis.floodguard.business;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Map;
import org.junit.jupiter.api.Test;

class RiskCalculatorTest {
    @Test void calculatesConfiguredRisk() {
        var calculator = new RiskCalculator(RiskCalculator.Weights.defaults());
        double score = calculator.score(Map.of(
                "flood", 1.0, "population", 0.8, "buildingDamage", 0.6,
                "roadAccessibility", 0.7, "medicalAccessibility", 0.5));
        assertEquals(0.775, score, 1.0e-9);
        assertEquals(RiskCalculator.Level.EXTREME, calculator.level(score));
    }

    @Test void rejectsInvalidWeightsAndIndicators() {
        assertThrows(IllegalArgumentException.class, () -> new RiskCalculator.Weights(1, 1, 1, 1, 1));
        var calculator = new RiskCalculator(RiskCalculator.Weights.defaults());
        assertThrows(IllegalArgumentException.class, () -> calculator.score(Map.of("flood", 1.2)));
    }
}
