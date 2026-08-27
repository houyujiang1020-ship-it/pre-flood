package com.mapgis.floodguard.business;

import java.util.*;

/** Business ranking over supplied network routes; not a replacement for MapGIS network analysis. */
public final class ResourceDispatcher {
    public record Resource(String id, String type, String node, int capacity) {
        public Resource {
            if (id == null || id.isBlank() || type == null || type.isBlank()
                    || node == null || node.isBlank() || capacity < 0) {
                throw new IllegalArgumentException("Invalid resource");
            }
        }
    }
    public record Recommendation(Resource resource, EmergencyRouter.RouteResult route) {}
    @FunctionalInterface public interface RouteProvider {
        Optional<EmergencyRouter.RouteResult> find(String start, String destination);
    }

    public List<Recommendation> recommend(Collection<Resource> resources, String type,
                                           String destination, int requiredCapacity, RouteProvider routes) {
        if (requiredCapacity <= 0 || destination == null || destination.isBlank() || type == null || type.isBlank()) {
            throw new IllegalArgumentException("Type, destination and positive required capacity are required");
        }
        List<Recommendation> results = new ArrayList<>();
        for (Resource resource : resources) {
            if (resource.type().equals(type) && resource.capacity() >= requiredCapacity) {
                routes.find(resource.node(), destination).ifPresent(route -> results.add(new Recommendation(resource, route)));
            }
        }
        results.sort(Comparator.comparingDouble((Recommendation r) -> r.route().estimatedMinutes())
                .thenComparing(r -> r.resource().id()));
        return List.copyOf(results);
    }
}
