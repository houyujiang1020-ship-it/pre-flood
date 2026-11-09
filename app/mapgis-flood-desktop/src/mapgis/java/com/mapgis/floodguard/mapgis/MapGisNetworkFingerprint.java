package com.mapgis.floodguard.mapgis;

import com.zondy.mapgis.geodatabase.net.ElemType;
import com.zondy.mapgis.geodatabase.net.NetCls;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Fingerprint of the opened network topology and edge geometry, independent of edge order. */
public final class MapGisNetworkFingerprint {
    private MapGisNetworkFingerprint() {}
    public static String calculate(NetCls network) {
        if (network==null || !network.hasOpened()) throw new IllegalArgumentException("MapGIS network is not open");
        long[] ids=network.queryID(0,ElemType.egdeElemType);
        if (ids==null || ids.length==0 || ids.length!=network.getEdgeCount())
            throw new IllegalStateException("MapGIS edge inventory is incomplete");
        Arrays.sort(ids);
        try {
            MessageDigest digest=MessageDigest.getInstance("SHA-256");
            digest.update((network.getURL()+"\n"+network.getNodCount()+"\n").getBytes(StandardCharsets.UTF_8));
            long previous=0;
            for (long raw:ids) {
                int edge=Math.toIntExact(raw);
                if (edge<=0 || raw==previous) throw new IllegalStateException("Invalid or duplicate MapGIS edge ID");
                previous=raw;
                double metres=MapGisNetworkLength.geometryMetres(network,edge);
                String line=edge+":"+network.getEdgeFromNod(edge)+":"+network.getEdgeToNod(edge)+":"
                        +Long.toHexString(Double.doubleToLongBits(metres))+"\n";
                digest.update(line.getBytes(StandardCharsets.UTF_8));
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (java.security.NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
    }
}
