package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.ExerciseTravelTime;
import com.zondy.mapgis.geodatabase.net.*;
import java.nio.file.*;
import java.util.*;

/** Called only with the newly created exercise network; never opens arbitrary operational networks for writing. */
final class MapGisExerciseWeights {
    static final String LENGTH_WEIGHT="fg_length_metres";
    static void prepare(NetCls network, int sourceClassId, Map<String,List<Integer>> mapping, Path source, Path output) throws Exception {
        var json=new ObjectMapper();
        Map<String,Object> evidence=new LinkedHashMap<>();
        evidence.put("scenario_only",true);
        evidence.put("dispatch_ready",false);
        evidence.put("length_weight_verified",false);
        evidence.put("network_url",network.getURL());
        NetCls reader=null;
        try {
            var scenario=json.readTree(source.resolve("scenario.json").toFile());
            if (!scenario.path("scenario_only").asBoolean() || scenario.path("speed_is_measured").asBoolean(true))
                throw new IllegalArgumentException("Only explicitly hypothetical exercise speed is accepted");
            double speed=scenario.path("assumed_speed_kph").asDouble(Double.NaN);
            ExerciseTravelTime.minutes(1,speed);
            evidence.put("assumed_speed_kph",speed);
            evidence.put("speed_is_measured",false);
            evidence.put("routing_strategy","MapGIS native system minimum-distance mode; uniform exercise speed makes it equivalent to minimum time");
            evidence.put("distance_source","verified projected edge geometry; custom MapGIS field weight is diagnostic only");
            Set<Integer> edges=new TreeSet<>(); mapping.values().forEach(edges::addAll);
            if (edges.size()!=network.getEdgeCount()) throw new IllegalStateException("Source mappings do not cover every native edge");
            Map<Integer,Double> lengths=new LinkedHashMap<>();
            List<Map<String,Object>> lengthChecks=new ArrayList<>();
            evidence.put("edge_length_checks",lengthChecks);
            Set<Integer> nodes=new TreeSet<>();
            for (int edge:edges) {
                double networkLength=network.getEdgeLength(edge), geometryLength=MapGisNetworkLength.geometryMetres(network,edge);
                lengthChecks.add(Map.of("edge_id",edge,"network_metres",networkLength,"geometry_metres",geometryLength));
                // getEdgeLength is known to be the SDK's default unit value here. Geometry is authoritative
                // until the registered mpLength network weight has been created and read back.
                lengths.put(edge,geometryLength);
            }
            NetFeature registeredSource=sourceClassId>0 ? network.getNetSFCls(sourceClassId) : null;
            if (registeredSource==null) throw new IllegalStateException("Verified exercise road class is not registered in the network: "+sourceClassId);
            registeredSource.dispose();
            NetWeight createdWeight=network.getWeight(LENGTH_WEIGHT);
            if (createdWeight==null) throw new IllegalStateException("Length weight supplied during network creation is missing");
            int weightId;
            try { weightId=createdWeight.getWgtID(); } finally { createdWeight.dispose(); }
            long exactFieldId=network.getWeightFldID(sourceClassId,LENGTH_WEIGHT);
            if (exactFieldId<=0) exactFieldId=network.getWeightFldID(sourceClassId,weightId);
            if (exactFieldId<=0) throw new IllegalStateException(
                    "Length weight is not bound to exercise road class "+sourceClassId);
            int fieldId=Math.toIntExact(exactFieldId);
            evidence.put("length_weight_id",weightId); evidence.put("length_weight_field_id",fieldId);
            evidence.put("default_getEdgeLength_is_not_used",true);
            for (int edge:edges) {
                int from=Math.toIntExact(network.getEdgeFromNod(edge)), to=Math.toIntExact(network.getEdgeToNod(edge));
                if (from<=0 || to<=0) throw new IllegalStateException("Invalid native endpoint for edge "+edge);
                nodes.add(from); nodes.add(to);
            }
            // A fresh reader avoids reusing NetCls after close; validates values visible through another handle.
            reader=new NetCls(); require(reader.openByURL(network.getURL()),"open weight reader",0);
            NetWeight persistedWeight=reader.getWeight(LENGTH_WEIGHT);
            if (persistedWeight==null) throw new IllegalStateException("Registered length weight is not persisted");
            int persistedWeightId;
            try { persistedWeightId=persistedWeight.getWgtID(); }
            finally { persistedWeight.dispose(); }
            evidence.put("persisted_length_weight_id",persistedWeightId);
            boolean completeCustomWeight=true;
            for (var entry:lengths.entrySet()) {
                Object value=reader.getWeightValue(entry.getKey(),persistedWeightId,ElemType.egdeElemType);
                evidence.putIfAbsent("native_weight_value_type",NativeWeightValue.type(value));
                evidence.putIfAbsent("native_weight_value_sample",String.valueOf(value));
                try { check(NativeWeightValue.asDouble(value),entry.getValue()); }
                catch (IllegalStateException error) {
                    evidence.put("failed_edge_id",entry.getKey());
                    evidence.put("failed_edge_value_type",NativeWeightValue.type(value));
                    evidence.put("failed_edge_value",String.valueOf(value));
                    evidence.put("failed_edge_expected_metres",entry.getValue());
                    evidence.put("custom_weight_diagnostic",error.toString());
                    completeCustomWeight=false;
                    break;
                }
            }
            evidence.put("edge_length_metres",lengths); evidence.put("native_node_ids",nodes);
            evidence.put("length_weight_verified",completeCustomWeight);
            evidence.put("native_geometry_lengths_verified",true);
            evidence.put("native_minimum_distance_mode_ready",true);
            evidence.put("minute_defaults_verified",true);
            evidence.put("warning",completeCustomWeight
                    ? "Registered native length weight verified; native minimum-distance mode is used for uniform-speed exercise routing."
                    : "MapGIS custom weight readback is incomplete, so it is not passed to JNI analysis. Native system minimum-distance mode is used; uniform exercise speed preserves the same route ordering. Real traffic and operational minute weights remain unverified.");
        } catch (Exception | LinkageError error) {
            evidence.put("error",error.toString()); throw error;
        } finally {
            try { if (reader!=null) reader.close(); }
            finally { Files.writeString(output.resolve("dispatch-preparation.json"),json.writerWithDefaultPrettyPrinter().writeValueAsString(evidence),StandardOpenOption.CREATE_NEW); }
        }
    }
    private static void require(long result,String step,int id) {
        if (result<=0) throw new IllegalStateException(step+" failed for "+id+": "+result);
    }
    private static void check(double actual,double expected) {
        if (!Double.isFinite(actual) || Math.abs(actual-expected)>1e-7*Math.max(1,Math.abs(expected)))
            throw new IllegalStateException("Native minute weight readback mismatch: "+actual+" vs "+expected);
    }
}
