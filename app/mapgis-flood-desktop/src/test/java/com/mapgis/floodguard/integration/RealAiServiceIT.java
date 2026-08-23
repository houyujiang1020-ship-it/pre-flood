package com.mapgis.floodguard.integration;

import static org.junit.jupiter.api.Assertions.*;

import com.mapgis.floodguard.ai.AiServiceClient;
import java.nio.file.Files;
import java.nio.file.Path;
import java.net.URI;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class RealAiServiceIT {
    @Test void javaCallsRunningPythonService() throws Exception {
        String url = System.getProperty("ai.url");
        assertNotNull(url, "Run with -Dai.url=http://127.0.0.1:8765");
        var health = new AiServiceClient(URI.create(url)).health();
        assertEquals("ok", health.status());
        assertTrue(health.model_loaded());
        assertNotNull(health.backend());

        String pre = System.getProperty("demo.pre");
        String post = System.getProperty("demo.post");
        String output = System.getProperty("demo.output");
        if (pre != null && post != null && output != null) {
            var client = new AiServiceClient(URI.create(url));
            var job = client.submit(Path.of(pre), Path.of(post), Path.of(output));
            Instant deadline = Instant.now().plusSeconds(30);
            while (!"completed".equals(job.status()) && !"failed".equals(job.status()) && Instant.now().isBefore(deadline)) {
                Thread.sleep(100);
                job = client.job(job.job_id());
            }
            assertEquals("completed", job.status(), job.error());
            assertTrue(Files.isRegularFile(Path.of(job.result().path("mask_path").asText())));
            assertTrue(job.result().path("statistics").path("flood_pixels").asLong() > 0);
        }
    }
}
