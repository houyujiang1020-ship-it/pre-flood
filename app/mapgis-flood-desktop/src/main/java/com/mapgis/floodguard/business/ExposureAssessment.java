package com.mapgis.floodguard.business;

import java.util.*;

/** Entity-level aggregation of spatial-query hits, not pixel/patch counts or verified damage. */
public final class ExposureAssessment {
    public enum Kind { BUILDING, ROAD }
    public record Hit(String dataset, String featureId, Kind kind, String patchId) {
        public Hit {
            if (dataset == null || dataset.isBlank() || featureId == null || featureId.isBlank()
                    || patchId == null || patchId.isBlank() || kind == null)
                throw new IllegalArgumentException("Entity identity and patch evidence are required");
        }
    }
    public record Entity(String dataset, String featureId, Kind kind, List<String> patchIds) {}
    public record Result(List<Entity> entities, long candidateBuildings, long candidateRoads) {}
    private record Key(String dataset, String id, Kind kind) {}
    public Result aggregate(Collection<Hit> hits) {
        Objects.requireNonNull(hits);
        Map<Key, Set<String>> grouped = new LinkedHashMap<>();
        for (Hit hit : hits) grouped.computeIfAbsent(new Key(hit.dataset(), hit.featureId(), hit.kind()),
                key -> new TreeSet<>()).add(hit.patchId());
        List<Entity> entities = grouped.entrySet().stream()
                .map(e -> new Entity(e.getKey().dataset(), e.getKey().id(), e.getKey().kind(), List.copyOf(e.getValue())))
                .sorted(Comparator.comparing(Entity::dataset).thenComparing(Entity::kind).thenComparing(Entity::featureId)).toList();
        return new Result(entities, entities.stream().filter(e -> e.kind() == Kind.BUILDING).count(),
                entities.stream().filter(e -> e.kind() == Kind.ROAD).count());
    }
}
