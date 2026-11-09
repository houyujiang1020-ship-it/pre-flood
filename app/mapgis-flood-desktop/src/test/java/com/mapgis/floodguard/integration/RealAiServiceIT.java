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
        if (System.getProperty("ai.expectedBackend") != null) assertEquals(System.getProperty("ai.expectedBackend"), health.backend());
        if (System.getProperty("ai.expectedDevice") != null) assertEquals(System.getProperty("ai.expectedDevice"), health.device());

        String pre = System.getProperty("demo.pre");
        String post = System.getProperty("demo.post");
        String output = System.getProperty("demo.output");
        assertNotNull(pre, "demo.pre required: health alone is not an inference integration test");
        assertNotNull(post, "demo.post required");
        assertNotNull(output, "demo.output required");
        {
            var client = new AiServiceClient(URI.create(url));
            var job = client.submit(Path.of(pre), Path.of(post), Path.of(output));
            Instant deadline = Instant.now().plusSeconds(30);
            while (!"completed".equals(job.status()) && !"failed".equals(job.status()) && Instant.now().isBefore(deadline)) {
                Thread.sleep(100);
                job = client.job(job.job_id());
            }
            assertEquals("completed", job.status(), job.error());
            var contract = com.mapgis.floodguard.ai.InferenceContract.verify(job);
            assertEquals("FALLBACK", contract.path("execution_mode").asText());
            assertThrows(IllegalStateException.class, () -> com.mapgis.floodguard.ai.InferenceContract.requireBridgeReady(contract));
            assertTrue(Files.isRegularFile(Path.of(job.result().path("mask_path").asText())));
            assertTrue(Files.isRegularFile(Path.of(job.result().path("preview_path").asText())));
            var statistics = job.result().path("statistics");
            assertEquals(health.backend(), statistics.path("backend").asText());
            long total = statistics.path("total_pixels").asLong();
            long flooded = statistics.path("flood_pixels").asLong();
            assertTrue(total > 0 && flooded >= 0 && flooded <= total);
            String report = new com.mapgis.floodguard.report.HtmlInferenceReport().render(
                    "真实 HTTP 推理记录", Path.of(pre), Path.of(post), job.result());
            Path reportPath = Path.of(job.result().path("mask_path").asText()).resolveSibling("识别记录.html");
            Files.writeString(reportPath, report, java.nio.charset.StandardCharsets.UTF_8, java.nio.file.StandardOpenOption.CREATE_NEW);
            assertTrue(Files.readString(reportPath).contains("data:image/png;base64,"));
        }
    }
}
