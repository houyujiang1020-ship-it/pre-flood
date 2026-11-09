package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ResourceDispatcherTest {
    @Test void splitsDemandAndReportsUnmetCapacity() {
        var resources = List.of(new ResourceDispatcher.Resource("a","rescue","A",4), new ResourceDispatcher.Resource("b","rescue","B",3));
        var plan = new ResourceDispatcher().plan(resources,"rescue","target",10,
                (s,t) -> Optional.of(new EmergencyRouter.RouteResult(List.of(s,t),List.of("road"),1,2)));
        assertEquals(3,plan.unfulfilled());
        assertEquals(7,plan.allocations().stream().mapToInt(ResourceDispatcher.Allocation::assignedCapacity).sum());
    }
    @Test void rejectsDuplicateResourcesAndInvalidRouteMetrics() {
        var resource = new ResourceDispatcher.Resource("same","rescue","A",4);
        assertThrows(IllegalArgumentException.class, () -> new ResourceDispatcher().plan(List.of(resource,resource),"rescue","B",1,(s,t)->Optional.empty()));
        assertThrows(IllegalArgumentException.class, () -> new EmergencyRouter.RouteResult(List.of("a"),List.of(),0,Double.NaN));
    }
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
