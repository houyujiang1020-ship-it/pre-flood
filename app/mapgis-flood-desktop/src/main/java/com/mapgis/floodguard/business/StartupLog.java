package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/** Persist observed startup checkpoints; a preflight is never a license assertion. */
public final class StartupLog {
    private final Path output;
    private final Map<String,Object> state=new LinkedHashMap<>();
    public StartupLog(Path output) {
        this.output=output;
        state.put("started_at",Instant.now().toString());
        state.put("sdk","UNVERIFIED"); state.put("plugin","UNVERIFIED");
        state.put("map","UNVERIFIED"); state.put("exceptions",new ArrayList<String>());
    }
    public void checkpoint(String key,String value) throws Exception {
        if (!Set.of("sdk","plugin","map").contains(key)) throw new IllegalArgumentException(key);
        state.put(key,value); save();
    }
    @SuppressWarnings("unchecked")
    public void failure(Throwable error) throws Exception {
        ((List<String>)state.get("exceptions")).add(error.toString()); save();
    }
    public void save() throws Exception {
        state.put("updated_at",Instant.now().toString());
        Path parent=output.toAbsolutePath().normalize().getParent(); Files.createDirectories(parent);
        Files.writeString(output,new ObjectMapper().writerWithDefaultPrettyPrinter().writeValueAsString(state));
    }
}
