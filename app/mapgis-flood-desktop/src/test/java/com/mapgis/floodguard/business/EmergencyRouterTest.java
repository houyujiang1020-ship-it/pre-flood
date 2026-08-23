package com.mapgis.floodguard.business;

import static org.junit.jupiter.api.Assertions.*;
import java.util.List;
import org.junit.jupiter.api.Test;

class EmergencyRouterTest {
    @Test void avoidsImpassableShortcutAndPenalizesFlooding() {
        var edges = List.of(
                new RoadEdge("blocked", "A", "D", 1, 40, RoadEdge.FloodLevel.IMPASSABLE),
                new RoadEdge("wet", "A", "B", 1, 30, RoadEdge.FloodLevel.SEVERE),
                new RoadEdge("safe1", "A", "C", 2, 60, RoadEdge.FloodLevel.NORMAL),
                new RoadEdge("safe2", "C", "D", 2, 60, RoadEdge.FloodLevel.NORMAL),
                new RoadEdge("wet2", "B", "D", 1, 30, RoadEdge.FloodLevel.SEVERE));
        var route = new EmergencyRouter().safestRoute(edges, "A", "D");
        assertEquals(List.of("A", "C", "D"), route.nodes());
        assertEquals(4.0, route.distanceKm(), 1e-9);
        assertEquals(4.0, route.estimatedMinutes(), 1e-9);
    }

    @Test void reportsUnreachableDestination() {
        var edges = List.of(new RoadEdge("x", "A", "B", 1, 30, RoadEdge.FloodLevel.IMPASSABLE));
        assertThrows(IllegalStateException.class, () -> new EmergencyRouter().safestRoute(edges, "A", "B"));
    }
}
