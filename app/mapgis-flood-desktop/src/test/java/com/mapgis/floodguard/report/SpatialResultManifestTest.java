package com.mapgis.floodguard.report;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.RasterGrid;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class SpatialResultManifestTest {
    @TempDir Path dir;
    private final RasterGrid grid = new RasterGrid(512,512,"WGS84",7,50,.00001,-.00001);
    private Map<String, SpatialResultManifest.RasterEvidence> outputs() throws Exception {
        var entries = new LinkedHashMap<String, SpatialResultManifest.RasterEvidence>();
        var names = new ArrayList<>(SpatialResultManifest.CLASSES);
        names.addAll(List.of("flood_mask", "overlay"));
        for (String name : names) {
            Path file = Files.createFile(dir.resolve(name + ".tif"));
            entries.put(name, new SpatialResultManifest.RasterEvidence(file.toString(), grid));
        }
        return entries;
    }
    @Test void recordsEvidenceWithoutClaimingFullAcceptance() throws Exception {
        Path destination = dir.resolve("spatial-result.json");
        new SpatialResultManifest().write(destination, dir.resolve("pre"), dir.resolve("post"), grid, outputs(), null);
        var report = new ObjectMapper().readTree(destination.toFile());
        assertTrue(report.path("grid_verified").asBoolean());
        assertFalse(report.path("map_rendering_verified").asBoolean());
        assertFalse(report.path("damage_analysis_completed").asBoolean());
        assertEquals(6, report.path("outputs").size());
    }
    @Test void rejectsIncompleteOrMisalignedResult() throws Exception {
        var data = outputs();
        data.remove("flooded_road");
        assertThrows(IllegalArgumentException.class, () -> new SpatialResultManifest().write(dir.resolve("x"), dir, dir, grid, data, null));
        data.put("flooded_road", new SpatialResultManifest.RasterEvidence(dir.resolve("flooded_road.tif").toString(),
                new RasterGrid(512,512,"OTHER",7,50,.00001,-.00001)));
        assertThrows(IllegalArgumentException.class, () -> new SpatialResultManifest().write(dir.resolve("x"), dir, dir, grid, data, null));
        assertFalse(Files.exists(dir.resolve("x")));
    }
    @Test void neverOverwritesExistingEvidence() throws Exception {
        var data = outputs();
        Path file = dir.resolve("record.json"); Files.writeString(file, "existing");
        assertThrows(FileAlreadyExistsException.class, () -> new SpatialResultManifest().write(file, dir, dir, grid, data, null));
        assertEquals("existing", Files.readString(file));
    }
}
