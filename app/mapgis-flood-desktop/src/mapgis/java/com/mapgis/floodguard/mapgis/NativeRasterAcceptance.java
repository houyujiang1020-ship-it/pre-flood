package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.util.*;

/** Real SDK batch check. Does not initialize/alter licensing or pretend to test desktop rendering. */
public final class NativeRasterAcceptance {
    public static void main(String[] args) throws Exception {
        if (args.length!=4) throw new IllegalArgumentException("pre.tif post.tif spatial-mask.tif output-directory required");
        Path destination=Files.createDirectory(Path.of(args[3]));
        Map<String,Object> record=new LinkedHashMap<>();
        record.put("engine","MapGIS installed native SDK"); record.put("desktop_rendering_verified",false);
        try {
            var spatializer=new MapGisRasterSpatializer();
            spatializer.validatePair(Path.of(args[0]),Path.of(args[1]));
            record.put("reference",spatializer.inspect(Path.of(args[0])));
            record.put("mask",spatializer.inspect(Path.of(args[2])));
            spatializer.inspect(Path.of(args[0])).requireSame(spatializer.inspect(Path.of(args[2])));
            new MapGisMaskVectorizer().export(Path.of(args[2]),destination.resolve("patches.geojson"));
            record.put("raster_and_vectorization_passed",true);
        } catch (Exception | LinkageError error) {
            record.put("raster_and_vectorization_passed",false); record.put("error",error.toString());
            throw error;
        } finally {
            Files.writeString(destination.resolve("native-acceptance.json"),new ObjectMapper().writerWithDefaultPrettyPrinter().writeValueAsString(record),StandardOpenOption.CREATE_NEW);
        }
    }
}
