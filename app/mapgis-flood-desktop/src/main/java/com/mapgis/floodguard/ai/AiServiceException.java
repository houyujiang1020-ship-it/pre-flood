package com.mapgis.floodguard.ai;

import java.io.IOException;

public final class AiServiceException extends IOException {
    private final int statusCode;

    public AiServiceException(int statusCode, String responseBody) {
        super("AI service returned HTTP " + statusCode + ": " + responseBody);
        this.statusCode = statusCode;
    }

    public int statusCode() {
        return statusCode;
    }
}
