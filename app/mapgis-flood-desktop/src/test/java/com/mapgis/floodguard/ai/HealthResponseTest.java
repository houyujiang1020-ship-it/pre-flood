package com.mapgis.floodguard.ai;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class HealthResponseTest {
    @Test void reportsRealBackendWithoutClaimingProductionReadiness() {
        String text = new HealthResponse("ok", true, "cuda", "siamunet-smoke", false).displaySummary();
        assertTrue(text.contains("已训练烟测模型"));
        assertTrue(text.contains("cuda"));
        assertFalse(text.contains("fallback"));
        assertTrue(text.contains("不可用于实际应急决策"));
    }
    @Test void unknownBackendIsNotPresentedAsFallback() {
        assertTrue(new HealthResponse("ok", false, "cpu", "unknown", false).displaySummary().contains("未验证后端"));
    }
    @Test void reportsConfiguredFallback() {
        assertTrue(new HealthResponse("ok", true, "cpu", "spectral-change-fallback", false).displaySummary().contains("非训练模型"));
    }
}
