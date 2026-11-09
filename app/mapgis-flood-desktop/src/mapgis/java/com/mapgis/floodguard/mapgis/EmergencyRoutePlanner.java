package com.mapgis.floodguard.mapgis;

import com.mapgis.floodguard.business.RoadImpedance;
import com.zondy.mapgis.analysis.networkanalysis.NetAnalyse;
import com.zondy.mapgis.analysis.networkanalysis.PathMode;
import com.zondy.mapgis.analysis.networkanalysis.PathWgtParam;
import com.zondy.mapgis.geodatabase.net.*;
import java.util.*;

/** Flood-aware routing through MapGIS NetAnalyse only; all temporary network costs are restored. */
public final class EmergencyRoutePlanner {
    public record Route(List<Integer> nodes,List<Integer> edges,double distanceMetres,
                        double impedanceMetres,double estimatedMinutes,String riskLevel) {}
    public record Result(Route original,Route optimized,Set<Integer> blockedEdges,
                         int dangerousEdgesAvoided,boolean detour) {}
    private record Weights(double forward,double reverse) {}

    public Result plan(NetCls network,int startNode,int targetNode,
                       Map<Integer,RoadImpedance.Status> statuses,double speedKph) {
        Objects.requireNonNull(network); Objects.requireNonNull(statuses);
        if (!network.hasOpened() || startNode<=0 || targetNode<=0)
            throw new IllegalArgumentException("请选择已打开的 MapGIS 网络和两个有效节点");
        if (network.getNodeInfo(startNode)==null || network.getNodeInfo(targetNode)==null)
            throw new IllegalArgumentException("起终点不在 MapGIS 网络中");
        if (!Double.isFinite(speedKph) || speedKph<=0 || speedKph>130)
            throw new IllegalArgumentException("请输入明确的演练通行速度（0,130] km/h");
        if (startNode==targetNode) {
            Route zero=new Route(List.of(startNode),List.of(),0,0,0,"LOW");
            return new Result(zero,zero,Set.of(),0,false);
        }
        synchronized (network) {
            long[] ids=network.queryID(0,ElemType.egdeElemType);
            if (ids==null || ids.length==0 || ids.length>200_000)
                throw new IllegalStateException("MapGIS 未返回可枚举的网络边，或路网超出交互上限");
            if (ids.length!=network.getEdgeCount())
                throw new IllegalStateException("MapGIS 边枚举数与网络边总数不一致，不能设置完整动态阻抗");
            Map<Integer,Weights> saved=new LinkedHashMap<>();
            Map<Integer,Double> lengths=new HashMap<>();
            Set<Integer> known=new HashSet<>();
            for (long raw:ids) {
                int edge=Math.toIntExact(raw);
                if (edge<=0 || !known.add(edge)) throw new IllegalStateException("MapGIS 网络边 ID 无效或重复");
                lengths.put(edge,MapGisNetworkLength.geometryMetres(network,edge));
                double forward=network.getEdgeDefaultWgt(edge,true),reverse=network.getEdgeDefaultWgt(edge,false);
                if (!Double.isFinite(forward) || !Double.isFinite(reverse) || forward<0 || reverse<0)
                    throw new IllegalStateException("MapGIS 原始阻抗无法读取："+edge);
                saved.put(edge,new Weights(forward,reverse));
            }
            if (!known.containsAll(statuses.keySet())) throw new IllegalArgumentException("灾损状态包含非当前路网的边 ID");
            Set<Integer> blocked=new TreeSet<>();
            for (var entry:statuses.entrySet()) if (entry.getValue()==RoadImpedance.Status.BLOCKED) blocked.add(entry.getKey());
            Throwable failure=null;
            try {
                for (int edge:known) setCost(network,edge,lengths.get(edge));
                Route original=route(network,startNode,targetNode,Set.of(),lengths,Map.of(),speedKph);
                if (original==null) throw new IllegalStateException("封路前 MapGIS 路网不连通");
                for (int edge:known) {
                    var status=statuses.getOrDefault(edge,RoadImpedance.Status.NORMAL);
                    setCost(network,edge,RoadImpedance.costMetres(lengths.get(edge),status));
                }
                Route optimized=route(network,startNode,targetNode,blocked,lengths,statuses,speedKph);
                if (optimized==null) throw new IllegalStateException("封路后没有可达救援路线");
                Set<Integer> dangerous=new HashSet<>(blocked);
                for (var entry:statuses.entrySet()) if (entry.getValue()==RoadImpedance.Status.HIGH_RISK) dangerous.add(entry.getKey());
                dangerous.retainAll(original.edges()); dangerous.removeAll(optimized.edges());
                return new Result(original,optimized,Set.copyOf(blocked),dangerous.size(),
                        !original.edges().equals(optimized.edges()));
            } catch (RuntimeException | Error error) { failure=error; throw error; }
            finally {
                Throwable restoreFailure=null;
                for (var entry:saved.entrySet()) {
                    int edge=entry.getKey(); Weights weight=entry.getValue();
                    try {
                        require(network.setEdgeDefaultWgt(edge,true,weight.forward()),"恢复正向阻抗 "+edge);
                        require(network.setEdgeDefaultWgt(edge,false,weight.reverse()),"恢复反向阻抗 "+edge);
                    } catch (RuntimeException | Error error) {
                        if (restoreFailure==null) restoreFailure=error; else restoreFailure.addSuppressed(error);
                    }
                }
                if (restoreFailure!=null) {
                    if (failure!=null) failure.addSuppressed(restoreFailure);
                    else if (restoreFailure instanceof Error error) throw error;
                    else throw (RuntimeException)restoreFailure;
                }
            }
        }
    }
    private static void setCost(NetCls network,int edge,double cost) {
        require(network.setEdgeDefaultWgt(edge,true,cost),"设置正向阻抗 "+edge);
        require(network.setEdgeDefaultWgt(edge,false,cost),"设置反向阻抗 "+edge);
        double read=network.getEdgeDefaultWgt(edge,true),reverse=network.getEdgeDefaultWgt(edge,false);
        if (!Double.isFinite(read) || !Double.isFinite(reverse)
                || Math.abs(read-cost)>1e-6*Math.max(1,cost) || Math.abs(reverse-cost)>1e-6*Math.max(1,cost))
            throw new IllegalStateException("MapGIS 阻抗读回不一致："+edge);
    }
    private static Route route(NetCls network,int from,int to,Set<Integer> blocked,
                               Map<Integer,Double> lengths,Map<Integer,RoadImpedance.Status> statuses,double speedKph) {
        NetAnalyse analysis=new NetAnalyse(); PathWgtParam weights=new PathWgtParam();
        NetFlagList flags=new NetFlagList(); NetBarrierList barriers=new NetBarrierList(); PathInfos paths=null;
        try {
            require(analysis.setNetCls(network),"设置网络");
            if (!weights.setPathMode(PathMode.systemMode_MinCost) || !analysis.setNetAnalyOption(network,weights))
                throw new IllegalStateException("MapGIS 最小成本模式不可用");
            flags.append(new NetFlag(FlagType.nodeType,from,0,"start"));
            flags.append(new NetFlag(FlagType.nodeType,to,0,"target")); analysis.setNetFlagList(flags);
            for (int edge:blocked) barriers.append(new NetBarrier(BarrierType.edgType,edge,0.5));
            analysis.setNetBarList(barriers);
            paths=analysis.pathAnalyse(false,false);
            if (paths==null) throw new IllegalStateException("MapGIS 路径分析未返回结果");
            if (paths.size()==0) return null;
            PathInfo path=paths.get(0); var edges=path.getEdges(); var nodes=path.getNodes();
            if (edges==null || nodes==null || edges.size()==0 || nodes.size()<2) return null;
            if (nodes.get(0)!=from || nodes.get(nodes.size()-1)!=to)
                throw new IllegalStateException("MapGIS 路径端点与请求不一致");
            List<Integer> resultEdges=new ArrayList<>(),resultNodes=new ArrayList<>();
            double metres=0,cost=0; boolean flooded=false,high=false;
            for (int i=0;i<edges.size();i++) {
                int encoded=edges.get(i);
                int edge=Math.abs(encoded);
                if (blocked.contains(edge)) throw new IllegalStateException("MapGIS 路线包含阻断道路");
                Double length=lengths.get(edge);
                if (length==null) throw new IllegalStateException("路径边不在已核验路网中："+edge);
                var status=statuses.getOrDefault(edge,RoadImpedance.Status.NORMAL);
                metres+=length; cost+=RoadImpedance.costMetres(length,status);
                flooded|=status==RoadImpedance.Status.FLOODED;
                high|=status==RoadImpedance.Status.HIGH_RISK;
                resultEdges.add(edge);
            }
            for (int i=0;i<nodes.size();i++) resultNodes.add(nodes.get(i));
            double nativeCost=path.getPathWgt();
            if (!Double.isFinite(nativeCost) || Math.abs(nativeCost-cost)>Math.max(1,cost)*.01)
                throw new IllegalStateException("MapGIS 返回成本与动态阻抗不一致，不能宣称优化路线：SDK="+nativeCost+" 期望="+cost);
            // Risk multipliers are optimization penalties, not measured travel-time factors.
            double minutes=metres/1000/speedKph*60;
            return new Route(List.copyOf(resultNodes),List.copyOf(resultEdges),metres,cost,minutes,
                    high?"HIGH":flooded?"MEDIUM":"LOW");
        } finally {
            if (paths!=null) paths.dispose(); analysis.dispose(); flags.dispose(); barriers.dispose(); weights.dispose();
        }
    }
    private static void require(long value,String action) { if (value<=0) throw new IllegalStateException(action+"失败："+value); }
}
