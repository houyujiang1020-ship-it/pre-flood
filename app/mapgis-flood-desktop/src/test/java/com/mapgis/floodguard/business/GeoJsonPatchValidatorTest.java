package com.mapgis.floodguard.business;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class GeoJsonPatchValidatorTest {
    private final RasterGrid grid = new RasterGrid(100,100,"EPSG4326",7,50,.01,-.01);
    @Test void acceptsClosedGeographicPatch() throws Exception {
        var polygon = new ObjectMapper().readTree("{\"type\":\"Polygon\",\"coordinates\":[[[7,50],[8,50],[8,49],[7,50]]]}");
        assertDoesNotThrow(() -> GeoJsonPatchValidator.validate(polygon,grid));
    }
    @Test void rejectsPixelCoordinates() throws Exception {
        var polygon = new ObjectMapper().readTree("{\"type\":\"Polygon\",\"coordinates\":[[[0,0],[100,0],[100,100],[0,0]]]}");
        assertThrows(IllegalArgumentException.class, () -> GeoJsonPatchValidator.validate(polygon,grid));
    }
    @Test void rejectsUnclosedAndWrongGeometry() throws Exception {
        var polygon = new ObjectMapper().readTree("{\"type\":\"Polygon\",\"coordinates\":[[[7,50],[8,50],[8,49],[7,49]]]}");
        assertThrows(IllegalArgumentException.class, () -> GeoJsonPatchValidator.validate(polygon,grid));
        assertThrows(IllegalArgumentException.class, () -> GeoJsonPatchValidator.validate(new ObjectMapper().createObjectNode(),grid));
    }
}
