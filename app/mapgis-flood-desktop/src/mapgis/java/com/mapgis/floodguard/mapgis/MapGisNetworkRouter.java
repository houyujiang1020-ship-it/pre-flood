package com.mapgis.floodguard.mapgis;

import com.mapgis.floodguard.business.EmergencyRouter.RouteResult;
import com.mapgis.floodguard.business.ResourceDispatcher.RouteProvider;
import com.zondy.mapgis.analysis.networkanalysis.NetAnalyse;
import com.zondy.mapgis.analysis.networkanalysis.PathMode;
import com.zondy.mapgis.analysis.networkanalysis.PathWgtParam;
import com.zondy.mapgis.geodatabase.net.*;
import java.util.*;

/** Uses MapGIS native routing, never silently falls back to the Java test router. */
public final class MapGisNetworkRouter implements RouteProvider {
    private final NetCls network; // Borrowed, opened and owned by the host.
    private final Map<String, Integer> nodeIds;
    private final Set<Integer> blockedEdges;
    private final String forwardMinutes, reverseMinutes, nodeMinutes;
    private final double kilometersPerNetworkUnit;
    private double exerciseSpeedKph=Double.NaN;

    /** Constant-speed exercise only: native minimum-distance paths, then explicit time conversion. */
    static MapGisNetworkRouter exercise(NetCls network, Map<String,Integer> nodes, Set<Integer> blocked, double speed) {
        com.mapgis.floodguard.business.ExerciseTravelTime.minutes(1,speed);
        var router=new MapGisNetworkRouter(network,nodes,blocked,"unused","unused","unused",0.001);
        router.exerciseSpeedKph=speed;
        return router;
    }

    public MapGisNetworkRouter(NetCls network, Map<String, Integer> nodeIds, Set<Integer> blockedEdges,
                               String forwardMinutes, String reverseMinutes, String nodeMinutes, double kilometersPerNetworkUnit) {
        this.network = Objects.requireNonNull(network);
        this.nodeIds = Map.copyOf(nodeIds); this.blockedEdges = Set.copyOf(blockedEdges);
        if (forwardMinutes == null || forwardMinutes.isBlank() || reverseMinutes == null || reverseMinutes.isBlank()
                || nodeMinutes == null || nodeMinutes.isBlank() || !Double.isFinite(kilometersPerNetworkUnit) || kilometersPerNetworkUnit <= 0)
            throw new IllegalArgumentException("Registered minute weights and explicit linear distance units are required");
        this.forwardMinutes = forwardMinutes; this.reverseMinutes = reverseMinutes; this.nodeMinutes = nodeMinutes;
        this.kilometersPerNetworkUnit = kilometersPerNetworkUnit;
    }

    @Override public synchronized Optional<RouteResult> find(String start, String destination) {
        if (!network.hasOpened()) throw new IllegalStateException("MapGIS 网络尚未打开");
        Integer from = nodeIds.get(start), to = nodeIds.get(destination);
        if (from == null || to == null || from <= 0 || to <= 0) throw new IllegalArgumentException("Unknown network node");
        if (network.getNodeInfo(from)==null || network.getNodeInfo(to)==null)
            throw new IllegalArgumentException("Node ID not present in selected native network");
        if (from.equals(to)) return Optional.of(new RouteResult(List.of(start), List.of(), 0, 0));
        NetAnalyse analysis = new NetAnalyse();
        PathWgtParam weights = new PathWgtParam();
        NetFlagList flags = new NetFlagList();
        NetBarrierList barriers = new NetBarrierList();
        PathInfos paths = null;
        try {
            if (analysis.setNetCls(network) <= 0) throw new IllegalStateException("MapGIS 设置网络失败");
            boolean exercise=Double.isFinite(exerciseSpeedKph);
            // Uniform speed means minimum distance and minimum travel time have identical
            // ordering. Built-in mode never hands the incomplete custom-weight array to JNI.
            boolean configured=exercise ? weights.setPathMode(PathMode.systemMode_MinDis)
                    : weights.setPathMode(PathMode.userDefine)
                    && weights.addWeight(WgtUsedType.usedDownedge, forwardMinutes)
                    && weights.addWeight(WgtUsedType.usedUpedge, reverseMinutes)
                    && weights.addWeight(WgtUsedType.usedNod, nodeMinutes);
            if (!configured || !analysis.setNetAnalyOption(network, weights))
                throw new IllegalStateException("MapGIS 路径权重模式配置失败");
            flags.append(new NetFlag(FlagType.nodeType, from, 0, start));
            flags.append(new NetFlag(FlagType.nodeType, to, 0, destination));
            analysis.setNetFlagList(flags);
            for (int edge : blockedEdges) {
                if (edge <= 0) throw new IllegalArgumentException("Invalid blocked edge ID");
                barriers.append(new NetBarrier(BarrierType.edgType, edge, 0.5));
            }
            analysis.setNetBarList(barriers);
            paths = analysis.pathAnalyse(false, false);
            if (paths == null) throw new IllegalStateException("MapGIS 未返回路径结果，不能视为路网已验收");
            if (paths.size() == 0) return Optional.empty();
            PathInfo path = paths.get(0);
            var edges = path.getEdges(); var nodes = path.getNodes();
            // This SDK returns one empty PathInfo (rather than an empty PathInfos)
            // when barriers disconnect an otherwise valid request.
            boolean emptyPath=edges!=null && nodes!=null && edges.size()==0 && nodes.size()<2;
            if (emptyPath && !blockedEdges.isEmpty()) return Optional.empty();
            if (edges == null || nodes == null || edges.size()==0 || nodes.size()<2
                    || nodes.get(0)!=from.intValue() || nodes.get(nodes.size()-1)!=to.intValue())
                throw new IllegalStateException("Native route endpoints are incomplete or differ from request");
            List<String> roadIds = new ArrayList<>(), routeNodes = new ArrayList<>();
            double distance = 0;
            for (int i = 0; i < edges.size(); i++) {
                int edge = Math.abs(edges.get(i));
                if (blockedEdges.contains(edge)) throw new IllegalStateException("MapGIS 路径包含阻断边，拒绝输出安全路线");
                double geometryLength=MapGisNetworkLength.geometryMetres(network,edge);
                double length=geometryLength;
                if (!Double.isFinite(length) || length < 0) throw new IllegalStateException("Invalid native edge length");
                distance += length * kilometersPerNetworkUnit; roadIds.add(Integer.toString(edge));
            }
            for (int i = 0; i < nodes.size(); i++) routeNodes.add(Integer.toString(nodes.get(i)));
            double minutes = exercise ? com.mapgis.floodguard.business.ExerciseTravelTime.minutes(distance*1000,exerciseSpeedKph) : path.getPathWgt();
            if (!Double.isFinite(minutes) || minutes < 0) throw new IllegalStateException("Invalid native route impedance");
            return Optional.of(new RouteResult(List.copyOf(routeNodes), List.copyOf(roadIds), distance, minutes));
        } finally {
            if (paths != null) paths.dispose();
            analysis.dispose(); flags.dispose(); barriers.dispose(); weights.dispose();
        }
    }
}
