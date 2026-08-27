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
        if (from.equals(to)) return Optional.of(new RouteResult(List.of(start), List.of(), 0, 0));
        NetAnalyse analysis = new NetAnalyse();
        PathWgtParam weights = new PathWgtParam();
        NetFlagList flags = new NetFlagList();
        NetBarrierList barriers = new NetBarrierList();
        PathInfos paths = null;
        try {
            if (analysis.setNetCls(network) <= 0) throw new IllegalStateException("MapGIS 设置网络失败");
            if (!weights.setPathMode(PathMode.userDefine)
                    || !weights.addWeight(WgtUsedType.usedDownedge, forwardMinutes)
                    || !weights.addWeight(WgtUsedType.usedUpedge, reverseMinutes)
                    || !weights.addWeight(WgtUsedType.usedNod, nodeMinutes)
                    || !analysis.setNetAnalyOption(network, weights))
                throw new IllegalStateException("MapGIS 设置分钟阻抗权失败，请先创建并更新网络权");
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
            List<String> roadIds = new ArrayList<>(), routeNodes = new ArrayList<>();
            double distance = 0;
            for (int i = 0; i < edges.size(); i++) {
                int edge = Math.abs(edges.get(i));
                if (blockedEdges.contains(edge)) throw new IllegalStateException("MapGIS 路径包含阻断边，拒绝输出安全路线");
                double length = network.getEdgeLength(edge);
                if (!Double.isFinite(length) || length < 0) throw new IllegalStateException("Invalid native edge length");
                distance += length * kilometersPerNetworkUnit; roadIds.add(Integer.toString(edge));
            }
            for (int i = 0; i < nodes.size(); i++) routeNodes.add(Integer.toString(nodes.get(i)));
            double minutes = path.getPathWgt();
            if (!Double.isFinite(minutes) || minutes < 0) throw new IllegalStateException("Invalid native route impedance");
            return Optional.of(new RouteResult(List.copyOf(routeNodes), List.copyOf(roadIds), distance, minutes));
        } finally {
            if (paths != null) paths.dispose();
            analysis.dispose(); flags.dispose(); barriers.dispose(); weights.dispose();
        }
    }
}
