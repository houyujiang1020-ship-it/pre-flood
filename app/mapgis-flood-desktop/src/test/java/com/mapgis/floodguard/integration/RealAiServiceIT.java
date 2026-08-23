package com.mapgis.floodguard.integration;

import static org.junit.jupiter.api.Assertions.*;

import com.mapgis.floodguard.ai.AiServiceClient;
import java.net.URI;
import org.junit.jupiter.api.Test;

class RealAiServiceIT {
    @Test void javaCallsRunningPythonService() throws Exception {
        String url = System.getProperty("ai.url");
        assertNotNull(url, "Run with -Dai.url=http://127.0.0.1:8765");
        var health = new AiServiceClient(URI.create(url)).health();
        assertEquals("ok", health.status());
        assertTrue(health.model_loaded());
        assertNotNull(health.backend());
    }
}
