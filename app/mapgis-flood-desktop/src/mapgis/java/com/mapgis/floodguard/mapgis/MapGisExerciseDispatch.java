package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.*;
import com.mapgis.floodguard.business.ResourceDispatcher;
import com.zondy.mapgis.geodatabase.SFeatureCls;
import com.zondy.mapgis.geodatabase.net.NetCls;
import com.zondy.mapgis.geometry.*;
import java.nio.file.*;
import java.util.*;

/** Read-only exercise acceptance. No dispatch commands or operational-network writes. */
final class MapGisExerciseDispatch {
    static void verify(NetCls net, String roadsUrl, Map<String,Long> sourceIds,
                       Map<String,List<Integer>> edges, Path source, Path output) throws Exception {
        var json=new ObjectMapper(); var evidence=new LinkedHashMap<String,Object>();
        evidence.put("scenario_only",true); evidence.put("dispatch_ready",false);
        evidence.put("exercise_routes_verified",false);
        evidence.put("routing_mode","MapGIS native system minimum-distance; verified projected geometry length; uniform hypothetical speed conversion; no turn/node delay");
        evidence.put("network_url",net.getURL());
        SFeatureCls roads=new SFeatureCls();
        try {
            var scenario=readVerified(json,source,"scenario.json");
            var resources=readVerified(json,source,"resources.json");
            var original=readVerified(json,source,"roads.geojson");
            if (!scenario.path("scenario_only").asBoolean() || !resources.path("scenario_only").asBoolean()
                    || scenario.path("speed_is_measured").asBoolean(true)) throw new IllegalArgumentException("Exercise declarations required");
            double speed=scenario.path("assumed_speed_kph").asDouble(Double.NaN);
            com.mapgis.floodguard.business.ExerciseTravelTime.minutes(1,speed);
            evidence.put("assumed_speed_kph",speed);
            if (roads.openByURL(roadsUrl)<=0) throw new IllegalStateException("Cannot open exercise roads for binding");
            Map<String,Integer> nodes=new LinkedHashMap<>();
            List<Map<String,Object>> bindings=new ArrayList<>(); evidence.put("bindings",bindings);
            List<ResourceDispatcher.Resource> fleet=new ArrayList<>();
            for (var resource:resources.path("resources")) {
                if (!resource.path("scenario_only").asBoolean() || resource.path("is_real_asset").asBoolean(true))
                    throw new IllegalArgumentException("Non-exercise asset rejected");
                String id=resource.path("id").asText();
                if (id.isBlank() || nodes.containsKey(id) || id.equals("destination")) throw new IllegalArgumentException("Duplicate/missing resource ID");
                nodes.put(id,bind(id,resource,original,roads,net,sourceIds,bindings));
                fleet.add(new ResourceDispatcher.Resource(id,resource.path("type").asText(),id,resource.path("capacity").asInt(-1)));
            }
            nodes.put("destination",bind("destination",scenario.path("destination"),original,roads,net,sourceIds,bindings));
            evidence.put("node_bindings",nodes);
            var baseline=MapGisNetworkRouter.exercise(net,nodes,Set.of(),speed);
            var dispatcher=new ResourceDispatcher();
            int demand=scenario.path("demand").asInt(); String type=scenario.path("resource_type").asText();
            var basePlan=dispatcher.plan(fleet,type,"destination",demand,baseline);
            evidence.put("baseline_plan",basePlan);
            if (basePlan.allocations().stream().noneMatch(a -> !a.recommendation().route().roadIds().isEmpty()))
                throw new IllegalStateException("No nontrivial baseline route; cannot accept routing");
            List<Map<String,Object>> cases=new ArrayList<>(); evidence.put("closure_cases",cases);
            for (var test:scenario.path("scenarios")) {
                Set<Integer> blocked=new TreeSet<>();
                for (var road:test.path("closed_source_road_ids")) {
                    var mapped=edges.get(road.asText());
                    if (mapped==null || mapped.isEmpty()) throw new IllegalArgumentException("Unknown closure road");
                    blocked.addAll(mapped);
                }
                if (blocked.isEmpty()) continue;
                boolean exercised=basePlan.allocations().stream().anyMatch(a -> a.recommendation().route().roadIds().stream()
                        .anyMatch(id -> blocked.contains(Integer.parseInt(id))));
                var plan=dispatcher.plan(fleet,type,"destination",demand,MapGisNetworkRouter.exercise(net,nodes,blocked,speed));
                cases.add(Map.of("scenario",test.path("id").asText(),"blocked_native_edges",blocked,
                        "baseline_intersects_closure",exercised,"plan",plan));
                if (!exercised) throw new IllegalStateException("Closure did not intersect baseline; not a valid avoidance test");
            }
            if (cases.isEmpty()) throw new IllegalStateException("No closure acceptance case");
            evidence.put("exercise_routes_verified",true);
            evidence.put("warning","Only snapped-node exercise routes verified. Off-network access, real traffic, real assets and operational minute-weight routing remain unverified.");
        } catch (Exception | LinkageError error) { evidence.put("error",error.toString()); throw error; }
        finally {
            try { roads.close(); } finally {
                String details=json.writerWithDefaultPrettyPrinter().writeValueAsString(evidence);
                Files.writeString(output.resolve("exercise-dispatch.json"),details,StandardOpenOption.CREATE_NEW);
                Files.writeString(output.resolve("exercise-dispatch.html"),
                        new com.mapgis.floodguard.report.HtmlExerciseReport().render(
                                Boolean.TRUE.equals(evidence.get("exercise_routes_verified")),details),StandardOpenOption.CREATE_NEW);
            }
        }
    }
    private static JsonNode readVerified(ObjectMapper json,Path source,String name) throws Exception {
        if (Files.size(source.resolve(name))>10_000_000) throw new IllegalArgumentException("Exercise input exceeds size limit");
        byte[] bytes=Files.readAllBytes(source.resolve(name));
        String digest=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
        var manifest=json.readTree(source.resolve("manifest.json").toFile());
        if (!digest.equals(manifest.path("files").path(name).asText())) throw new IllegalArgumentException("Manifest mismatch: "+name);
        return json.readTree(bytes);
    }
    private static int bind(String label,JsonNode point,JsonNode original,SFeatureCls roads,NetCls net,
                            Map<String,Long> ids,List<Map<String,Object>> evidence) {
        String road=point.path("source_road_id").asText(); int index=point.path("source_vertex_index").asInt(-1);
        Long fid=ids.get(road); if (fid==null || index<0) throw new IllegalArgumentException("Invalid source vertex: "+label);
        JsonNode coordinates=null;
        for (var feature:original.path("features")) if (road.equals(feature.path("id").asText())) coordinates=feature.path("geometry").path("coordinates");
        if (coordinates==null || index>=coordinates.size()) throw new IllegalArgumentException("Missing original vertex");
        double longitude=point.path("longitude").asDouble(Double.NaN), latitude=point.path("latitude").asDouble(Double.NaN);
        if (!Double.isFinite(longitude) || !Double.isFinite(latitude)
                || Math.abs(coordinates.get(index).get(0).asDouble()-longitude)>1e-8
                || Math.abs(coordinates.get(index).get(1).asDouble()-latitude)>1e-8)
            throw new IllegalArgumentException("Ledger coordinates differ from source vertex");
        Geometry geometry=roads.getGeometry(fid);
        try {
            if (!(geometry instanceof GeoLine line)) throw new IllegalStateException("Native road is not a line");
            Dots dots=line.get2Dots();
            try {
                if (dots==null || dots.size()!=coordinates.size()) throw new IllegalStateException("Native vertices changed; explicit re-projection required");
                Dot location=dots.get(index); int node=Math.toIntExact(net.getNearNod(location,25));
                Map<String,Object> binding=new LinkedHashMap<>(); evidence.add(binding);
                binding.put("id",label); binding.put("source_road",road); binding.put("vertex",index);
                binding.put("source_projected_xy",List.of(location.getX(),location.getY()));
                binding.put("node_id",node); binding.put("max_snap_metres",25); binding.put("accepted",false);
                binding.put("off_network_travel_included",false);
                if (node<=0) throw new IllegalStateException("No native node within 25m for "+label);
                Dot snapped=new Dot(); if (net.getNodPos(node,snapped)<=0) throw new IllegalStateException("Native node position unavailable");
                double distance=Math.hypot(location.getX()-snapped.getX(),location.getY()-snapped.getY());
                binding.put("node_projected_xy",List.of(snapped.getX(),snapped.getY())); binding.put("snap_metres",distance);
                if (!Double.isFinite(distance) || distance>25) throw new IllegalStateException("Node snap exceeds 25m for "+label+": "+distance+"m, node="+node);
                binding.put("accepted",true);
                return node;
            } finally { if(dots!=null) dots.dispose(); }
        } finally { if(geometry!=null) geometry.dispose(); }
    }
}
