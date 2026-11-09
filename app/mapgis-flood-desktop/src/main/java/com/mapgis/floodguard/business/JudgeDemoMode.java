package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.time.*;
import java.util.*;

/** Records actual wall-clock competition milestones; never fabricates stage completion. */
public final class JudgeDemoMode {
    private static final Map<DemoController.Step,Integer> DEADLINES=Map.of(
            DemoController.Step.LOAD_DATA,30,DemoController.Step.AI_DETECTION,60,
            DemoController.Step.RISK_ASSESSMENT,120,DemoController.Step.ROUTE_PLANNING,180,
            DemoController.Step.FINAL_REPORT,240);
    private final ObjectMapper json=new ObjectMapper();
    private final Instant started;
    private final Map<String,Object> milestones=new LinkedHashMap<>();
    private String status="RUNNING", failure;
    public JudgeDemoMode() { this(Instant.now()); }
    JudgeDemoMode(Instant started) { this.started=Objects.requireNonNull(started); }
    public void completed(DemoController.Step step,Path evidence) {
        Integer deadline=DEADLINES.get(step); if (deadline==null) return;
        long elapsed=Duration.between(started,Instant.now()).toMillis();
        milestones.put(step.name(),Map.of("elapsed_ms",elapsed,"deadline_seconds",deadline,
                "within_target",elapsed<=deadline*1000L,"evidence",evidence.toString()));
    }
    public void finish(boolean success,String reason) {
        status=success?"COMPLETE":"FAILED"; failure=reason;
    }
    public Path save(Path output) throws Exception {
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("schema_version",1); result.put("started_at",started.toString());
        result.put("saved_at",Instant.now().toString()); result.put("status",status);
        result.put("failure",failure); result.put("milestones",milestones);
        result.put("targets_met",status.equals("COMPLETE") && milestones.size()==DEADLINES.size()
                && milestones.values().stream().allMatch(value->Boolean.TRUE.equals(((Map<?,?>)value).get("within_target"))));
        Files.createDirectories(output.toAbsolutePath().normalize().getParent());
        Files.writeString(output,json.writerWithDefaultPrettyPrinter().writeValueAsString(result),
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);
        return output;
    }
}
