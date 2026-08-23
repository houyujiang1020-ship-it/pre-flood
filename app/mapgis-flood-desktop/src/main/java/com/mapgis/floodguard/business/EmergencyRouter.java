package com.mapgis.floodguard.business;

import java.util.*;

public final class EmergencyRouter {
    public RouteResult safestRoute(Collection<RoadEdge> edges, String start, String destination) {
        Map<String, List<RoadEdge>> graph = new HashMap<>();
        for (RoadEdge edge : edges) {
            graph.computeIfAbsent(edge.from(), ignored -> new ArrayList<>()).add(edge);
            graph.computeIfAbsent(edge.to(), ignored -> new ArrayList<>()).add(
                    new RoadEdge(edge.id(), edge.to(), edge.from(), edge.distanceKm(), edge.speedKph(), edge.floodLevel()));
        }
        Map<String, Double> cost = new HashMap<>();
        Map<String, Step> previous = new HashMap<>();
        PriorityQueue<Node> queue = new PriorityQueue<>(Comparator.comparingDouble(Node::cost));
        cost.put(start, 0.0); queue.add(new Node(start, 0.0));
        while (!queue.isEmpty()) {
            Node current = queue.poll();
            if (current.cost() > cost.getOrDefault(current.name(), Double.POSITIVE_INFINITY)) continue;
            if (current.name().equals(destination)) break;
            for (RoadEdge edge : graph.getOrDefault(current.name(), List.of())) {
                if (!edge.passable()) continue;
                double candidate = current.cost() + edge.travelMinutes();
                if (candidate < cost.getOrDefault(edge.to(), Double.POSITIVE_INFINITY)) {
                    cost.put(edge.to(), candidate); previous.put(edge.to(), new Step(current.name(), edge));
                    queue.add(new Node(edge.to(), candidate));
                }
            }
        }
        if (!cost.containsKey(destination)) throw new IllegalStateException("No safe route from " + start + " to " + destination);
        LinkedList<String> nodes = new LinkedList<>();
        LinkedList<String> roads = new LinkedList<>();
        double distance = 0;
        String cursor = destination; nodes.addFirst(cursor);
        while (!cursor.equals(start)) {
            Step step = previous.get(cursor); roads.addFirst(step.edge().id()); distance += step.edge().distanceKm();
            cursor = step.node(); nodes.addFirst(cursor);
        }
        return new RouteResult(List.copyOf(nodes), List.copyOf(roads), distance, cost.get(destination));
    }

    public record RouteResult(List<String> nodes, List<String> roadIds, double distanceKm, double estimatedMinutes) {}
    private record Node(String name, double cost) {}
    private record Step(String node, RoadEdge edge) {}
}
