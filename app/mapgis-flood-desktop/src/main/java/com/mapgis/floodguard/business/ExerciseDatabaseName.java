package com.mapgis.floodguard.business;

import java.util.Objects;
import java.util.UUID;

/** MapGIS database names are limited to 32 bytes; ASCII makes this deterministic. */
public final class ExerciseDatabaseName {
    private ExerciseDatabaseName() {}
    public static String from(UUID id) {
        return "FG_" + Objects.requireNonNull(id).toString().replace("-", "").substring(0,24);
    }
}
