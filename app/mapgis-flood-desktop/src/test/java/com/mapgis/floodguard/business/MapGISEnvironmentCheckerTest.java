package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class MapGISEnvironmentCheckerTest {
    @TempDir Path temp;
    @Test void neverClaimsLicenseOrDllLoadFromFilesAlone() throws Exception {
        Path program=Files.createDirectory(temp.resolve("Program"));
        for (String jar:new String[]{"mapgis_pluginengine.jar","mapgis_geomap.jar","mapgis_geoobjects.jar",
                "mapgis_geodatabase.jar","mapgis_geoanalysis.jar","mapgis_ui_controls.jar"})
            Files.writeString(program.resolve(jar),"fixture");
        Files.writeString(program.resolve("native.dll"),"fixture");
        Path report=temp.resolve("environment_check.json");
        var result=new MapGISEnvironmentChecker().check(program,report,true,false,null);
        assertEquals("OK",result.mapgisSdk());
        assertEquals("PRESENT_UNVERIFIED",result.dllStatus());
        assertEquals("NOT_VERIFIED",result.license());
        assertEquals("NOT_STARTED",result.mapControl());
        assertEquals("READY",result.plugin());
        assertTrue(Files.isRegularFile(report));
        assertEquals("NOT_VERIFIED",new ObjectMapper().readTree(report.toFile()).path("license").asText());
    }
}
