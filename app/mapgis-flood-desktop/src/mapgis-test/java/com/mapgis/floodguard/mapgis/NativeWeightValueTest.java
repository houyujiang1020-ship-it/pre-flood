package com.mapgis.floodguard.mapgis;
import com.zondy.mapgis.common.ObjectRef;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class NativeWeightValueTest {
    @Test void acceptsDocumentedAndCompatibleNumericRepresentations() {
        assertEquals(12.5,NativeWeightValue.asDouble(12.5));
        assertEquals(12.5,NativeWeightValue.asDouble(" 12.5 "));
        assertEquals(12.5,NativeWeightValue.asDouble(new ObjectRef("12.5")));
    }
    @Test void rejectsOpaqueOrNonfiniteValues() {
        assertThrows(IllegalStateException.class,()->NativeWeightValue.asDouble(new byte[]{1}));
        assertThrows(IllegalStateException.class,()->NativeWeightValue.asDouble("NaN"));
        assertThrows(IllegalStateException.class,()->NativeWeightValue.asDouble(null));
    }
}
