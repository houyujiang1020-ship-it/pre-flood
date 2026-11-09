package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class RoadImpedanceTest {
    @Test void publishedFactorsAndNoZeroLength() {
        assertEquals(100,RoadImpedance.costMetres(100,RoadImpedance.Status.NORMAL));
        assertEquals(1000,RoadImpedance.costMetres(100,RoadImpedance.Status.FLOODED));
        assertEquals(5000,RoadImpedance.costMetres(100,RoadImpedance.Status.HIGH_RISK));
        assertEquals(99999900,RoadImpedance.costMetres(100,RoadImpedance.Status.BLOCKED));
        assertThrows(IllegalArgumentException.class,()->RoadImpedance.costMetres(0,RoadImpedance.Status.NORMAL));
    }
}
