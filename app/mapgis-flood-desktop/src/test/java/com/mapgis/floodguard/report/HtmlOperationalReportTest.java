package com.mapgis.floodguard.report;

import com.mapgis.floodguard.business.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class HtmlOperationalReportTest {
    private DispatchRequest request() {
        return new DispatchRequest("net","forward","reverse","node",.001,Map.of("A",1,"B",2),
                List.of(new ResourceDispatcher.Resource("<script>","boat","A",3)),"boat","B",5,List.of());
    }
    @Test void preservesUnknownsEscapesTextAndShowsShortage() {
        var e=new ExposureAssessment().aggregate(List.of());
        var c=new RoadClosurePlan().build(e,List.of(),(d,id)->List.of());
        var p=new ResourceDispatcher().plan(request().resources(),"boat","B",5,
                (a,b)->Optional.of(new EmergencyRouter.RouteResult(List.of("A","B"),List.of("7"),1,4)));
        String html=new HtmlOperationalReport().render(e,c,p,request(),"<script>source</script>");
        assertTrue(html.contains("未满足：2")); assertTrue(html.contains("不能填为0"));
        assertFalse(html.contains("<script>")); assertTrue(html.contains("&lt;script&gt;"));
    }
    @Test void requestJsonRoundTripAndUnknownNodeRejection() throws Exception {
        var json=new ObjectMapper(); var r=request();
        assertEquals(r,json.readValue(json.writeValueAsString(r),DispatchRequest.class));
        assertThrows(IllegalArgumentException.class,()->new DispatchRequest("net","f","r","n",1,
                Map.of("B",2),r.resources(),"boat","B",2,List.of()));
    }
}
