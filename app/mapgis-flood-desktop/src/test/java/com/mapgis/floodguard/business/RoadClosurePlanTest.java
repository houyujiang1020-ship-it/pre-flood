package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class RoadClosurePlanTest {
    private final ExposureAssessment.Result exposure = new ExposureAssessment().aggregate(List.of(
            new ExposureAssessment.Hit("roads","1",ExposureAssessment.Kind.ROAD,"p1"),
            new ExposureAssessment.Hit("roads","1",ExposureAssessment.Kind.ROAD,"p2")));
    @Test void intersectionIsNotAutomaticClosure() {
        var result=new RoadClosurePlan().build(exposure,List.of(),(d,id)->List.of(11,12));
        assertTrue(result.blockedEdges().isEmpty()); assertEquals(1,result.unreviewed());
    }
    @Test void blocksAllNativeSubEdgesAndDeduplicates() {
        var review=new RoadClosurePlan.Review("roads","1",RoadClosurePlan.Status.CLOSED,"现场封路记录-1");
        var result=new RoadClosurePlan().build(exposure,List.of(review),(d,id)->List.of(11,12,11));
        assertEquals(Set.of(11,12),result.blockedEdges()); assertEquals(0,result.unreviewed());
        assertThrows(UnsupportedOperationException.class,()->result.blockedEdges().add(13));
    }
    @Test void rejectsUnmappedRoadRatherThanPretendingPassable() {
        assertThrows(IllegalArgumentException.class,()->new RoadClosurePlan().build(exposure,List.of(),(d,id)->List.of()));
    }
    @Test void rejectsEvidenceFreeAndForeignReviews() {
        assertThrows(IllegalArgumentException.class,()->new RoadClosurePlan.Review("roads","1",RoadClosurePlan.Status.CLOSED,""));
        var review=new RoadClosurePlan.Review("other","1",RoadClosurePlan.Status.PASSABLE,"inspection");
        assertThrows(IllegalArgumentException.class,()->new RoadClosurePlan().build(exposure,List.of(review),(d,id)->List.of(11)));
    }
    @Test void rejectsDuplicateReviews() {
        var review=new RoadClosurePlan.Review("roads","1",RoadClosurePlan.Status.CLOSED,"inspection");
        assertThrows(IllegalArgumentException.class,()->new RoadClosurePlan().build(exposure,List.of(review,review),(d,id)->List.of(11)));
    }
}
