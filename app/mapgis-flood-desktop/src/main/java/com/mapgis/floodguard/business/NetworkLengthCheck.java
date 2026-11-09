package com.mapgis.floodguard.business;

/** Rejects placeholder/default network lengths before interpreting them as metres. */
public final class NetworkLengthCheck {
    private NetworkLengthCheck() {}
    public static void verify(double networkMetres,double geometryMetres) {
        if (!Double.isFinite(networkMetres) || !Double.isFinite(geometryMetres)
                || networkMetres<=0 || geometryMetres<=0
                || Math.abs(networkMetres-geometryMetres)>Math.max(0.1,geometryMetres*0.001))
            throw new IllegalStateException("Network length differs from native geometry: "+networkMetres+" vs "+geometryMetres+" metres");
    }
}
