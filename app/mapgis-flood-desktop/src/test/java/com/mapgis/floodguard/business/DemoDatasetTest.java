package com.mapgis.floodguard.business;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.*;

class DemoDatasetTest {
    @TempDir Path otherWorkingDirectory;

    @Test void writesProjectAuditWhenLaunchedOutsideRepository() throws Exception {
        Path root=DemoDataset.repositoryRoot();
        Path expected=root.resolve("outputs/demo-dataset-audit.json");
        String classpath=List.of(DemoDataset.class,ObjectMapper.class,JsonFactory.class,JsonProperty.class)
                .stream().map(type -> {
                    try { return Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toString(); }
                    catch (Exception error) { throw new IllegalStateException(error); }
                }).collect(Collectors.joining(System.getProperty("path.separator")));
        Path java=Path.of(System.getProperty("java.home"),"bin","java.exe");
        Process process=new ProcessBuilder(java.toString(),"-cp",classpath,DemoDataset.class.getName())
                .directory(otherWorkingDirectory.toFile()).redirectErrorStream(true).start();
        String output=new String(process.getInputStream().readAllBytes(),StandardCharsets.UTF_8).trim();
        assertEquals(0,process.waitFor(),output);
        assertTrue(output.contains("demo-dataset-audit.json"),output);
        assertTrue(Files.isRegularFile(expected));
        var audit=new ObjectMapper().readTree(expected.toFile());
        assertTrue(audit.has("missing_native_inputs"));
        assertFalse(audit.path("full_demo_ready").asBoolean());
    }

    @Test void preservesP007EvidenceWhenSourceAuditIsRepeated() throws Exception {
        Path report=otherWorkingDirectory.resolve("outputs/demo-dataset-audit.json");
        Files.createDirectories(report.getParent());
        Files.writeString(report,"{\"p007_replay\":{\"official_submission_status\":\"NOT_READY\"}}",
                StandardCharsets.UTF_8);
        new DemoDataset().audit(otherWorkingDirectory,report);
        var audit=new ObjectMapper().readTree(report.toFile());
        assertEquals("NOT_READY",audit.path("p007_replay").path("official_submission_status").asText());
        assertFalse(audit.path("full_demo_ready").asBoolean());
    }
}
