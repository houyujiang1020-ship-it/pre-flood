package com.mapgis.floodguard.business;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class RasterGridTest {
    private RasterGrid grid() { return new RasterGrid(512, 512, "WGS84", 7, 50, 0.00001, -0.00001); }
    @Test void acceptsSameGrid() { assertDoesNotThrow(() -> grid().requireSame(grid())); }
    @Test void rejectsShiftAndMissingCrs() {
        assertThrows(IllegalArgumentException.class, () -> grid().requireSame(new RasterGrid(512,512,"WGS84",7.00001,50,0.00001,-0.00001)));
        assertThrows(IllegalArgumentException.class, () -> new RasterGrid(512,512,"",7,50,0.00001,-0.00001));
    }
    @Test void rejectsDifferentCrsAndDimensions() {
        assertThrows(IllegalArgumentException.class, () -> grid().requireSame(new RasterGrid(512,512,"OTHER",7,50,0.00001,-0.00001)));
        assertThrows(IllegalArgumentException.class, () -> grid().requireSame(new RasterGrid(256,512,"WGS84",7,50,0.00001,-0.00001)));
    }
    @Test void restoresPixelCentreAfterResizeAndCrop() {
        var projected = new RasterGrid(100, 80, "PROJCS metre", 500, 1000, 2, -2);
        assertEquals(new RasterGrid.Point(502, 998), projected.modelPixelToMap(0, 0, 50, 40, 0, 0, 100, 80));
        assertEquals(new RasterGrid.Point(522, 978), projected.modelPixelToMap(0, 0, 10, 10, 10, 10, 20, 20));
        assertThrows(IllegalArgumentException.class,
                () -> projected.modelPixelToMap(0, 0, 10, 10, 90, 0, 20, 20));
    }
}
