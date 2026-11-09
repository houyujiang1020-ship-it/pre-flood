package com.mapgis.floodguard.business;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class NativeRoutingGateTest {
    @Test void allowsOnlyVerifiedWeight() {
        assertDoesNotThrow(()->NativeRoutingGate.require(true));
        assertThrows(IllegalStateException.class,()->NativeRoutingGate.require(false));
    }
}
