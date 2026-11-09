package com.mapgis.floodguard.business;

import java.util.*;

/** Explicit scenario closures: a model intersection alone is never a confirmed closure. */
public final class RoadClosurePlan {
    public enum Status { UNREVIEWED, PASSABLE, CLOSED }
    public record Review(String dataset, String featureId, Status status, String evidence) {
        public Review {
            if (dataset == null || dataset.isBlank() || featureId == null || featureId.isBlank() || status == null)
                throw new IllegalArgumentException("Road identity and review status required");
            if (status != Status.UNREVIEWED && (evidence == null || evidence.isBlank()))
                throw new IllegalArgumentException("Reviewed road requires evidence/source");
        }
    }
    public record MappedRoad(Review review, List<Integer> edgeIds) {}
    public record Result(List<MappedRoad> roads, Set<Integer> blockedEdges, long unreviewed) {}
    @FunctionalInterface public interface EdgeResolver { List<Integer> resolve(String dataset, String featureId); }

    public Result build(ExposureAssessment.Result exposure, Collection<Review> reviews, EdgeResolver resolver) {
        Map<List<String>, Review> indexed = new HashMap<>();
        for (Review review : reviews) {
            if (indexed.put(List.of(review.dataset(), review.featureId()), review) != null)
                throw new IllegalArgumentException("Duplicate road review");
        }
        List<MappedRoad> mapped = new ArrayList<>();
        Set<Integer> blocked = new TreeSet<>();
        long pending = 0;
        for (var entity : exposure.entities()) {
            if (entity.kind() != ExposureAssessment.Kind.ROAD) continue;
            Review review = indexed.remove(List.of(entity.dataset(), entity.featureId()));
            if (review == null) review = new Review(entity.dataset(),entity.featureId(),Status.UNREVIEWED,"");
            List<Integer> edges = resolver.resolve(entity.dataset(), entity.featureId());
            if (edges == null || edges.isEmpty() || edges.stream().anyMatch(e -> e == null || e <= 0))
                throw new IllegalArgumentException("Road has no valid native network mapping: " + entity.featureId());
            edges = edges.stream().distinct().sorted().toList();
            mapped.add(new MappedRoad(review, edges));
            if (review.status() == Status.CLOSED) blocked.addAll(edges);
            if (review.status() == Status.UNREVIEWED) pending++;
        }
        if (!indexed.isEmpty()) throw new IllegalArgumentException("Review refers to roads outside this exposure result");
        return new Result(List.copyOf(mapped), Collections.unmodifiableSet(blocked), pending);
    }
}
