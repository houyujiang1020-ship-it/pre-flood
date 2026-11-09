package com.mapgis.floodguard.mapgis;

import com.mapgis.floodguard.business.RoadClosurePlan;
import com.zondy.mapgis.geodatabase.SFeatureCls;
import com.zondy.mapgis.geodatabase.net.NetCls;
import java.util.*;

/** Uses source feature membership, not nearest-edge guessing or coincident numeric IDs. */
public final class MapGisRoadNetworkMapper implements RoadClosurePlan.EdgeResolver {
    private final NetCls network;
    private final SFeatureCls roads;
    private final String dataset;
    public MapGisRoadNetworkMapper(NetCls network, SFeatureCls roads, String dataset) {
        this.network = Objects.requireNonNull(network); this.roads = Objects.requireNonNull(roads); this.dataset = dataset;
    }
    @Override public List<Integer> resolve(String dataset, String featureId) {
        if (!Objects.equals(this.dataset,dataset) || !network.hasOpened() || !roads.hasOpened())
            throw new IllegalArgumentException("Road source/network unavailable or mismatched");
        // Compare database identity as well as class ID: IDs alone are not globally unique.
        var member = network.getSFCls(roads.getClsID());
        if (member == null || !Objects.equals(member.getURL(), roads.getURL()))
            throw new IllegalArgumentException("Selected roads are not a source feature class of this network");
        // The ledger field is a MapGIS source feature OID, not an arbitrary road label.
        int id;
        try { id = Integer.parseInt(featureId); }
        catch (NumberFormatException error) { throw new IllegalArgumentException("source_feature_id must be a MapGIS source OID",error); }
        if (id <= 0) throw new IllegalArgumentException("Invalid source feature ID");
        var source=roads.getAtt(id);
        if (source==null) throw new IllegalArgumentException("Source road OID does not exist: "+id);
        source.dispose();
        var nativeEdges = network.getSubEdgeS(roads.getClsID(), id);
        if (nativeEdges == null) throw new IllegalStateException("MapGIS returned no edge mapping");
        try {
            List<Integer> result = new ArrayList<>();
            for (int i=0;i<nativeEdges.size();i++) {
                int edge = nativeEdges.get(i);
                if (edge <= 0 || network.getEdgeFromNod(edge) <= 0 || network.getEdgeToNod(edge) <= 0)
                    throw new IllegalStateException("Invalid native network edge");
                result.add(edge);
            }
            return result;
        } finally { nativeEdges.dispose(); }
    }
}
