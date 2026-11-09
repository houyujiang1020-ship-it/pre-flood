package com.mapgis.floodguard.business;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class NetworkLengthCheckTest {
    @Test void acceptsSmallNumericDifference() { assertDoesNotThrow(()->NetworkLengthCheck.verify(100,100.01)); }
    @Test void rejectsPlaceholderLength() { assertThrows(IllegalStateException.class,()->NetworkLengthCheck.verify(1,100)); }
    @Test void rejectsInvalidGeometry() {
        assertThrows(IllegalStateException.class,()->NetworkLengthCheck.verify(1,Double.NaN));
        assertThrows(IllegalStateException.class,()->NetworkLengthCheck.verify(0,0));
    }
}
