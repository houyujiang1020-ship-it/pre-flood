package com.mapgis.floodguard.mapgis;
import com.zondy.mapgis.geodatabase.net.NetCls;
import com.zondy.mapgis.geometry.*;
final class MapGisNetworkLength {
    static double geometryMetres(NetCls network,int edge) {
        Dots points=network.getEdgePos(edge);
        GeoVarLine line=null;
        try {
            if (points==null || points.size()<2) throw new IllegalStateException("Missing native geometry for edge "+edge);
            line=new GeoVarLine(points);
            double metres=line.calLength();
            if (!Double.isFinite(metres) || metres<=0) throw new IllegalStateException("Invalid native geometry length for edge "+edge);
            return metres;
        } finally { if(line!=null) line.dispose(); if(points!=null) points.dispose(); }
    }
}
