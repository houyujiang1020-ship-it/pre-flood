package com.mapgis.floodguard.ai;

import com.fasterxml.jackson.databind.JsonNode;

public record JobResponse(String job_id, String status, int progress, String error, JsonNode result) {}
