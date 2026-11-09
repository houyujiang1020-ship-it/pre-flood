package com.mapgis.floodguard.business;

/** Explicitly separates official ground-truth validation from model output. */
public enum AnalysisMode {
    AI_PREDICTION("AI PREDICTION"),
    GROUND_TRUTH_VALIDATION("GT VALIDATION");

    private final String display;
    AnalysisMode(String display) { this.display = display; }
    public String display() { return display; }
    public boolean allowsAiInference() { return this == AI_PREDICTION; }
}
