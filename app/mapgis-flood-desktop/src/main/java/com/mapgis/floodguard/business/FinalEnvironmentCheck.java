package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/** Promotes only observed runtime states to final PASS; unknowns remain UNVERIFIED. */
public final class FinalEnvironmentCheck {
    private final ObjectMapper json=new ObjectMapper();
    public Path generate(Path environmentCheck,Path output) throws Exception {
        JsonNode source=Files.isRegularFile(environmentCheck)?json.readTree(environmentCheck.toFile()):null;
        String sdk=source!=null && "OK".equals(source.path("mapgis_sdk").asText())?"PASS":"UNVERIFIED";
        String map=source!=null && "READY".equals(source.path("map_control").asText())?"PASS":"UNVERIFIED";
        String plugin=source!=null && "READY".equals(source.path("plugin").asText())?"PASS":"UNVERIFIED";
        // A rendered MapControl proves the DLLs needed by that component loaded;
        // a directory full of DLL files proves only that files are present.
        String dll="PASS".equals(map)?"PASS":"UNVERIFIED";
        String license="UNVERIFIED";
        Map<String,Object> report=new LinkedHashMap<>();
        report.put("schema_version",1); report.put("checked_at",Instant.now().toString());
        report.put("sdk",sdk); report.put("dll",dll); report.put("license",license);
        report.put("mapcontrol",map); report.put("plugin",plugin);
        report.put("all_pass",List.of(sdk,dll,license,map,plugin).stream().allMatch("PASS"::equals));
        report.put("source",environmentCheck.toString());
        report.put("note","当前未集成官方只读许可证状态接口；即使静态报告写 READY，也不能自动认定许可证 PASS");
        Files.createDirectories(output.toAbsolutePath().normalize().getParent());
        Files.writeString(output,json.writerWithDefaultPrettyPrinter().writeValueAsString(report),
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);
        return output;
    }
    public static void main(String[] args) throws Exception {
        if (args.length!=2) throw new IllegalArgumentException("environment_check.json and final_environment_report.json required");
        System.out.println(new FinalEnvironmentCheck().generate(Path.of(args[0]),Path.of(args[1])).toAbsolutePath());
    }
}
