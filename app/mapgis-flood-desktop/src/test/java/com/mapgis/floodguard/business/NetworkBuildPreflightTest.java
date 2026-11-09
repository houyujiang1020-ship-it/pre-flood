package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class NetworkBuildPreflightTest {
    @Test void acceptsVerifiedDataset() {
        assertDoesNotThrow(() -> NetworkBuildPreflight.check(9,9,4,new int[]{4},20,20));
    }
    @Test void rejectsRootAndDifferentDataset() {
        assertThrows(IllegalStateException.class,() -> NetworkBuildPreflight.check(0,0,4,new int[]{4},20,20));
        assertThrows(IllegalStateException.class,() -> NetworkBuildPreflight.check(9,8,4,new int[]{4},20,20));
    }
    @Test void rejectsMissingClass() {
        assertThrows(IllegalStateException.class,() -> NetworkBuildPreflight.check(9,9,4,null,20,20));
        assertThrows(IllegalStateException.class,() -> NetworkBuildPreflight.check(9,9,4,new int[]{5},20,20));
    }
    @Test void rejectsLostOrEmptyRoads() {
        assertThrows(IllegalStateException.class,() -> NetworkBuildPreflight.check(9,9,4,new int[]{4},20,19));
        assertThrows(IllegalStateException.class,() -> NetworkBuildPreflight.check(9,9,4,new int[]{4},0,0));
    }
}
