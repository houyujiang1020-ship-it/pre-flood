package com.mapgis.floodguard.ai;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Objects;

public final class AiServiceClient {
    private final URI baseUri;
    private final HttpClient client;
    private final ObjectMapper mapper;

    public AiServiceClient(URI baseUri) {
        this(baseUri, HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build());
    }

    AiServiceClient(URI baseUri, HttpClient client) {
        this.baseUri = Objects.requireNonNull(baseUri).resolve("/");
        this.client = Objects.requireNonNull(client);
        this.mapper = new ObjectMapper().configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    }

    public HealthResponse health() throws IOException, InterruptedException {
        return sendJson(HttpRequest.newBuilder(baseUri.resolve("health")).GET().build(), HealthResponse.class);
    }

    public JobResponse submit(Path pre, Path post, Path output) throws IOException, InterruptedException {
        var body = mapper.writeValueAsString(new InferenceRequest(
                pre.toAbsolutePath().normalize().toString(),
                post.toAbsolutePath().normalize().toString(),
                output.toAbsolutePath().normalize().toString()));
        var request = HttpRequest.newBuilder(baseUri.resolve("inference/flood"))
                .header("Content-Type", "application/json; charset=UTF-8")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();
        return sendJson(request, JobResponse.class);
    }

    public JobResponse job(String jobId) throws IOException, InterruptedException {
        return sendJson(HttpRequest.newBuilder(baseUri.resolve("jobs/" + jobId)).GET().build(), JobResponse.class);
    }

    private <T> T sendJson(HttpRequest request, Class<T> type) throws IOException, InterruptedException {
        var response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new AiServiceException(response.statusCode(), response.body());
        }
        return mapper.readValue(response.body(), type);
    }
}
