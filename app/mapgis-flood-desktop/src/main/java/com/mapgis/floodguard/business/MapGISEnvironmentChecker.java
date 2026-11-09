package com.mapgis.floodguard.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/** Read-only MapGIS preflight. It never initializes or modifies a license. */
public final class MapGISEnvironmentChecker {
    private static final List<String> JARS=List.of("mapgis_pluginengine.jar","mapgis_geomap.jar",
            "mapgis_geoobjects.jar","mapgis_geodatabase.jar","mapgis_geoanalysis.jar","mapgis_ui_controls.jar");
    private final ObjectMapper json=new ObjectMapper();
    public static void main(String[] args) throws Exception {
        if (args.length!=2) throw new IllegalArgumentException("MapGIS Program directory and output JSON path required");
        var result=new MapGISEnvironmentChecker().check(Path.of(args[0]),Path.of(args[1]),false,false,null);
        System.out.println(result.report().toAbsolutePath());
    }
    public record Result(String mapgisSdk,String dllStatus,String license,String mapControl,String plugin,
                         List<String> missing,List<String> recommendations,Path report) {
        public boolean canCreateMap() { return "OK".equals(mapgisSdk) && !"MISSING".equals(dllStatus); }
    }
    public Result check(Path program,Path output,boolean pluginInvoked,boolean controlReady,Throwable failure) throws Exception {
        Objects.requireNonNull(program); Objects.requireNonNull(output);
        List<String> missing=new ArrayList<>(), advice=new ArrayList<>();
        for (String jar:JARS) if (!Files.isRegularFile(program.resolve(jar))) missing.add(jar);
        String sdk=missing.isEmpty()?"OK":"MISSING";
        boolean dllDirectory=Files.isDirectory(program);
        long dllCount=0;
        if (dllDirectory) try (var files=Files.list(program)) {
            dllCount=files.filter(p->p.getFileName().toString().toLowerCase(Locale.ROOT).endsWith(".dll")).count();
        }
        String dll=dllCount>0?"PRESENT_UNVERIFIED":"MISSING";
        if (dllCount==0) missing.add("MapGIS native DLL directory");
        if (!"OK".equals(sdk)) advice.add("安装与本插件构建版本匹配的 MapGIS 官方 SDK，并设置 floodguard.mapgis.home");
        if ("MISSING".equals(dll)) advice.add("检查 MapGIS Program 目录及 Windows PATH 中的原生 DLL");
        advice.add("授权状态需由官方 MapGIS 宿主在已授权账号下验证；文件检查不能证明许可证就绪");
        if (failure!=null) advice.add("检查 MapGIS 运行环境和授权状态；原始异常："+failure);
        String license="NOT_VERIFIED";
        String map=controlReady?"READY":failure==null?"NOT_STARTED":"FAILED";
        String plugin=pluginInvoked?"READY":"NOT_VERIFIED";
        Map<String,Object> data=new LinkedHashMap<>();
        data.put("schema_version",1); data.put("checked_at",Instant.now().toString());
        data.put("mapgis_sdk",sdk); data.put("dll_status",dll); data.put("license",license);
        data.put("map_control",map); data.put("plugin",plugin);
        data.put("mapgis_program",program.toAbsolutePath().normalize().toString());
        data.put("dll_count",dllCount); data.put("missing",missing); data.put("recommendations",advice);
        data.put("failure",failure==null?null:failure.toString());
        Path parent=output.toAbsolutePath().normalize().getParent(); Files.createDirectories(parent);
        Path temp=Files.createTempFile(parent,"environment-",".tmp");
        try { Files.writeString(temp,json.writerWithDefaultPrettyPrinter().writeValueAsString(data));
            Files.move(temp,output,StandardCopyOption.REPLACE_EXISTING); }
        finally { Files.deleteIfExists(temp); }
        return new Result(sdk,dll,license,map,plugin,List.copyOf(missing),List.copyOf(advice),output);
    }
}
