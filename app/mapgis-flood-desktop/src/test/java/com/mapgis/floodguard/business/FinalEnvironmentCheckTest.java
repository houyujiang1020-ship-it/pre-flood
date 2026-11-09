package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class FinalEnvironmentCheckTest {
    @TempDir Path temp;
    @Test void cannotInferLicensePassFromStaticOrUntrustedReadyFlag() throws Exception {
        Path source=Files.writeString(temp.resolve("environment_check.json"),
                "{\"mapgis_sdk\":\"OK\",\"dll_status\":\"PRESENT_UNVERIFIED\","+
                "\"license\":\"READY\",\"map_control\":\"NOT_STARTED\",\"plugin\":\"NOT_VERIFIED\"}");
        var result=new ObjectMapper().readTree(new FinalEnvironmentCheck().generate(source,
                temp.resolve("final_environment_report.json")).toFile());
        assertEquals("PASS",result.path("sdk").asText());
        assertEquals("UNVERIFIED",result.path("dll").asText());
        assertEquals("UNVERIFIED",result.path("license").asText());
        assertFalse(result.path("all_pass").asBoolean());
    }
}
