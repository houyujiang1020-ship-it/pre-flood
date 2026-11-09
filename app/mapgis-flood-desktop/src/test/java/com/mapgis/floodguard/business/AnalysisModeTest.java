package com.mapgis.floodguard.business;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;

class AnalysisModeTest {
    @Test void modesAreExplicitAndMutuallyExclusive() {
        assertTrue(AnalysisMode.AI_PREDICTION.allowsAiInference());
        assertFalse(AnalysisMode.GROUND_TRUTH_VALIDATION.allowsAiInference());
        assertEquals("GT VALIDATION", AnalysisMode.GROUND_TRUTH_VALIDATION.display());
    }
}
