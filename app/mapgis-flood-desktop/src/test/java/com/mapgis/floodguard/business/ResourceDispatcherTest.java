package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ResourceDispatcherTest {
    @Test void filtersCapacityTypeAndUnreachableThenRanksTime() {
        var resources = List.of(new ResourceDispatcher.Resource("fast", "hospital", "A", 20),
                new ResourceDispatcher.Resource("slow", "hospital", "B", 20),
                new ResourceDispatcher.Resource("small", "hospital", "C", 2),
                new ResourceDispatcher.Resource("blocked", "hospital", "D", 20),
                new ResourceDispatcher.Resource("other", "fire", "E", 20));
        var result = new ResourceDispatcher().recommend(resources, "hospital", "target", 10,
                (start, target) -> start.equals("D") ? Optional.empty() : Optional.of(
                        new EmergencyRouter.RouteResult(List.of(start, target), List.of(), 1, start.equals("A") ? 2 : 5)));
        assertEquals(List.of("fast", "slow"), result.stream().map(r -> r.resource().id()).toList());
    }
    @Test void rejectsInvalidNetworkInputs() {
        assertThrows(IllegalArgumentException.class, () -> new RoadEdge("x", "a", "b", -1, 30, RoadEdge.FloodLevel.NORMAL));
        assertThrows(IllegalArgumentException.class, () -> new RoadEdge("x", "a", "b", 1, 0, RoadEdge.FloodLevel.NORMAL));
        assertThrows(IllegalArgumentException.class, () -> new RoadEdge("x", "a", "b", Double.NaN, 30, RoadEdge.FloodLevel.NORMAL));
        assertThrows(IllegalArgumentException.class, () -> new DamageSummary(Double.NaN, 0, 0, 0, 0, 0));
    }
}
