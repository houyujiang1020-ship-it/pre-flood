package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;

/** Sequential evidence gate for the desktop exercise. */
public final class DemoController {
    public enum Step { LOAD_DATA, AI_DETECTION, DAMAGE_THEMATIC, RISK_ASSESSMENT,
        ROAD_CLOSURE, ROUTE_PLANNING, RESOURCE_MATCHING, FINAL_REPORT }
    @FunctionalInterface public interface Action {
        CompletionStage<Path> execute(Step step,ScenarioManager.Scenario scenario,Map<Step,Path> evidence) throws Exception;
    }
    public interface Listener {
        void started(Step step,int completed,int total);
        void completed(Step step,Path evidence,int completed,int total);
        void failed(Step step,Throwable error);
    }
    public record Result(Path directory,Path ledger,Map<Step,Path> evidence) {}
    private final ObjectMapper json=new ObjectMapper();

    public CompletionStage<Result> start(ScenarioManager.Scenario scenario,Path outputRoot,
                                         Action action,Listener listener) throws Exception {
        Objects.requireNonNull(scenario); Objects.requireNonNull(action); Objects.requireNonNull(listener);
        List<String> missing=scenario.missingForFullRun();
        if (!missing.isEmpty()) throw new IllegalArgumentException("案例缺少："+String.join("、",missing));
        Path directory=Files.createDirectories(outputRoot.resolve("demo-"+UUID.randomUUID()));
        Path ledger=directory.resolve("demo-progress.json");
        EnumMap<Step,Path> evidence=new EnumMap<>(Step.class);
        java.util.concurrent.atomic.AtomicReference<Step> active=new java.util.concurrent.atomic.AtomicReference<>();
        write(ledger,scenario,"RUNNING",null,null,evidence);
        CompletableFuture<Void> chain=CompletableFuture.completedFuture(null);
        Step[] steps=Step.values();
        for (int index=0;index<steps.length;index++) {
            Step step=steps[index]; int completed=index;
            chain=chain.thenCompose(ignored->{
                active.set(step);
                listener.started(step,completed,steps.length);
                try {
                    CompletionStage<Path> execution=action.execute(step,scenario,Collections.unmodifiableMap(evidence));
                    if (execution==null) throw new IllegalStateException("步骤未返回执行对象："+step);
                    return execution.toCompletableFuture().thenAccept(path->{
                        if (path==null || !Files.isRegularFile(path))
                            throw new CompletionException(new IllegalStateException("步骤缺少持久化证据："+step));
                        evidence.put(step,path.toAbsolutePath().normalize());
                        try { write(ledger,scenario,"RUNNING",step,null,evidence); }
                        catch (Exception error) { throw new CompletionException(error); }
                        listener.completed(step,path,completed+1,steps.length);
                    });
                } catch (Exception error) { return CompletableFuture.failedFuture(error); }
            });
        }
        return chain.handle((ignored,error)->{
            if (error!=null) {
                Throwable cause=error instanceof CompletionException && error.getCause()!=null?error.getCause():error;
                Step failed=active.get();
                try { write(ledger,scenario,"FAILED",failed,cause.toString(),evidence); }
                catch (Exception saveError) { cause.addSuppressed(saveError); }
                listener.failed(failed,cause);
                throw new CompletionException(cause);
            }
            try { write(ledger,scenario,"COMPLETE",Step.FINAL_REPORT,null,evidence); }
            catch (Exception saveError) { throw new CompletionException(saveError); }
            return new Result(directory,ledger,Collections.unmodifiableMap(new EnumMap<>(evidence)));
        });
    }
    private void write(Path ledger,ScenarioManager.Scenario scenario,String status,Step current,
                       String error,Map<Step,Path> evidence) throws Exception {
        Map<String,Object> data=new LinkedHashMap<>();
        data.put("schema_version",1); data.put("scenario",scenario.name()); data.put("simulated",scenario.simulated());
        data.put("status",status); data.put("current_step",current); data.put("updated_at",Instant.now().toString());
        data.put("error",error);
        Map<String,String> paths=new LinkedHashMap<>(); evidence.forEach((step,path)->paths.put(step.name(),path.toString()));
        data.put("evidence",paths);
        Path temp=Files.createTempFile(ledger.getParent(),"progress-",".tmp");
        try {
            Files.writeString(temp,json.writerWithDefaultPrettyPrinter().writeValueAsString(data));
            Files.move(temp,ledger,StandardCopyOption.REPLACE_EXISTING);
        } finally { Files.deleteIfExists(temp); }
    }
}
