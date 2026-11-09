package com.mapgis.floodguard.business;

import java.util.*;

/** Imported operational data. No invented resources, nodes or default minute weights. */
public record DispatchRequest(String networkUrl, String forwardMinutes, String reverseMinutes, String nodeMinutes,
        double kilometersPerNetworkUnit, Map<String,Integer> nodes, List<ResourceDispatcher.Resource> resources,
        String type, String destination, int demand, List<RoadClosurePlan.Review> reviews) {
    public DispatchRequest {
        for (String text : new String[]{networkUrl,forwardMinutes,reverseMinutes,nodeMinutes,type,destination})
            if (text == null || text.isBlank()) throw new IllegalArgumentException("Network, weights and dispatch fields required");
        if (!Double.isFinite(kilometersPerNetworkUnit) || kilometersPerNetworkUnit <= 0 || demand <= 0)
            throw new IllegalArgumentException("Explicit linear unit conversion and positive demand required");
        nodes = Map.copyOf(nodes); resources = List.copyOf(resources); reviews = List.copyOf(reviews);
        if (!nodes.containsKey(destination) || nodes.entrySet().stream().anyMatch(e -> e.getKey().isBlank() || e.getValue() <= 0))
            throw new IllegalArgumentException("Invalid network nodes/destination");
        Set<String> ids = new HashSet<>();
        for (var resource : resources) {
            if (!ids.add(resource.id()) || !nodes.containsKey(resource.node()))
                throw new IllegalArgumentException("Duplicate resource or unknown resource node");
        }
        if (resources.isEmpty()) throw new IllegalArgumentException("No resource inventory supplied");
    }
}
