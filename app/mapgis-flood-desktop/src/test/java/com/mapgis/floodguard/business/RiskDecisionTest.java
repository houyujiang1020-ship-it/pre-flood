package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class RiskDecisionTest {
    private static RiskDecision.Result evaluate(double b,double p,double r,double d) {
        return RiskDecision.evaluate(RiskDecision.scalar("building",b,"buildings"),
                RiskDecision.scalar("population",p,"flood-and-grid"),
                RiskDecision.scalar("road",r,"road-ledger"),
                RiskDecision.scalar("resource_distance",d,"area-field"));
    }
    @Test void canonicalFourFactorScoreAndLevels() {
        var result=evaluate(.4,.3,.2,.5);
        assertEquals(.34,result.riskScore(),1e-12);
        assertEquals("MEDIUM",result.riskLevel()); assertEquals("COMPLETE",result.status());
        assertEquals("LOW",evaluate(0,0,0,0).riskLevel());
        assertEquals("MEDIUM",evaluate(.75,0,0,0).riskLevel());
        assertEquals("HIGH",evaluate(1,0,1,0).riskLevel());
        assertEquals("HIGH",evaluate(1,1,1,1).riskLevel());
    }
    @Test void missingAndInvalidMetricsNeverBecomeLowRisk() {
        for (var missing:new RiskDecision.Metric[]{
                RiskDecision.ratio("building",0.0,0.0,"buildings"),
                RiskDecision.missing("building","无建筑",null),
                RiskDecision.scalar("building",Double.NaN,"buildings"),
                RiskDecision.scalar("building",Double.POSITIVE_INFINITY,"buildings"),
                RiskDecision.scalar("building",1.1,"buildings")}) {
            var result=RiskDecision.evaluate(missing,RiskDecision.scalar("population",0.0,"grid"),
                    RiskDecision.scalar("road",0.0,"roads"),RiskDecision.scalar("resource_distance",0.0,"resources"));
            assertEquals("PARTIAL",result.status()); assertNull(result.riskScore()); assertNull(result.riskLevel());
        }
        assertEquals("INVALID",RiskDecision.ratio("road",2.0,1.0,"roads").status());
        assertEquals("MISSING",RiskDecision.ratio("population",null,100.0,"grid").status());
        assertEquals("INVALID",RiskDecision.ratio("road",-1.0,100.0,"roads").status());
        assertEquals("MISSING",RiskDecision.scalar("resource_distance",.5,null).status());
        var noFlood=RiskDecision.evaluate(RiskDecision.scalar("building",.4,"buildings"),
                RiskDecision.missing("population","独立洪水面缺失",null),RiskDecision.scalar("road",.2,"roads"),
                RiskDecision.scalar("resource_distance",.5,"resources"));
        assertNull(noFlood.riskScore()); assertEquals("PARTIAL",noFlood.status());
    }
}
