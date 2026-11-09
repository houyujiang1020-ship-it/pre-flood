package com.mapgis.floodguard.business;

/** Prevents JNI path analysis from being called after an incomplete weight setup. */
public final class NativeRoutingGate {
    private NativeRoutingGate() {}
    public static void require(boolean weightReady) {
        if (!weightReady) throw new IllegalStateException("Registered network weight was not verified; native routing is disabled");
    }
}
