package com.mapgis.floodguard.ai;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class AiServiceClientTest {
    private HttpServer server;
    private AiServiceClient client;
    private final AtomicReference<String> requestBody = new AtomicReference<>();

    @BeforeEach void start() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/health", exchange -> respond(exchange, 200,
                "{\"status\":\"ok\",\"model_loaded\":true,\"device\":\"cpu\",\"backend\":\"test\",\"production_checkpoint_loaded\":false}"));
        server.createContext("/inference/flood", exchange -> {
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            respond(exchange, 202, "{\"job_id\":\"abc\",\"status\":\"queued\",\"progress\":0}");
        });
        server.createContext("/jobs/abc", exchange -> respond(exchange, 200,
                "{\"job_id\":\"abc\",\"status\":\"completed\",\"progress\":100,\"result\":{\"mask_path\":\"输出/flood.png\"}}"));
        server.start();
        client = new AiServiceClient(URI.create("http://127.0.0.1:" + server.getAddress().getPort()));
    }

    @AfterEach void stop() { server.stop(0); }

    @Test void rejectsMalformedJobIdBeforeRequest() {
        assertThrows(IllegalArgumentException.class, () -> client.job("../health"));
        assertThrows(IllegalArgumentException.class, () -> client.job("abc?x=1"));
        assertThrows(IllegalArgumentException.class, () -> client.job(null));
    }

    @Test void exposesHttpFailure() {
        AiServiceException error = assertThrows(AiServiceException.class, () -> client.job("missing"));
        assertNotNull(error.getMessage());
    }

    @Test void healthAndJobsDeserialize() throws Exception {
        assertEquals("ok", client.health().status());
        assertEquals("abc", client.submit(Path.of("灾前.png"), Path.of("灾后.png"), Path.of("输出")).job_id());
        assertTrue(requestBody.get().contains("灾前.png"));
        assertEquals("completed", client.job("abc").status());
    }

    private static void respond(com.sun.net.httpserver.HttpExchange exchange, int status, String json) throws java.io.IOException {
        byte[] body = json.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
        exchange.sendResponseHeaders(status, body.length);
        exchange.getResponseBody().write(body);
        exchange.close();
    }
}
