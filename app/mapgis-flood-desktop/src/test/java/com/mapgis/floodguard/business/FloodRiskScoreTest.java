package com.mapgis.floodguard.business;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class FloodRiskScoreTest {
    @Test void weightsAndBoundariesAreExact() {
        var score = FloodRiskScore.calculate(.5,1,.5,.5);
        assertEquals(.65,score.score(),1e-12);
        assertEquals(FloodRiskScore.Level.HIGH,score.level());
        assertEquals(FloodRiskScore.Level.MEDIUM,FloodRiskScore.calculate(.75,0,0,0).level());
        assertEquals(FloodRiskScore.Level.HIGH,FloodRiskScore.calculate(1,0,1,0).level());
    }
    @Test void rejectsMissingDenominatorsAndOutOfRangeInputs() {
        assertThrows(IllegalArgumentException.class,()->FloodRiskScore.ratio(0,0,"population"));
        assertThrows(IllegalArgumentException.class,()->FloodRiskScore.ratio(2,1,"roads"));
        assertThrows(IllegalArgumentException.class,()->FloodRiskScore.calculate(.2,.3,.4,Double.NaN));
    }
}
