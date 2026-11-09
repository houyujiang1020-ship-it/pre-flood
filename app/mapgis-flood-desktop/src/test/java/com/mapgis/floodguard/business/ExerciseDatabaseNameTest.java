package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;

class ExerciseDatabaseNameTest {
    @Test void staysWithinNativeNameLimit() {
        for (int i=0;i<1000;i++) {
            String name=ExerciseDatabaseName.from(UUID.randomUUID());
            assertEquals(27,name.getBytes(StandardCharsets.UTF_8).length);
            assertTrue(name.matches("FG_[0-9a-f]{24}"));
        }
    }
    @Test void keepsStableIdentityPrefix() {
        assertEquals("FG_123456781234123412341234",ExerciseDatabaseName.from(UUID.fromString("12345678-1234-1234-1234-123456789abc")));
    }
}
