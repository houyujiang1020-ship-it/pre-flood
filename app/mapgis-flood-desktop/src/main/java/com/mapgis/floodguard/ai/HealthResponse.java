package com.mapgis.floodguard.ai;

public record HealthResponse(
        String status,
        boolean model_loaded,
        String device,
        String backend,
        boolean production_checkpoint_loaded) {}
