package com.mapgis.floodguard.business;

/** Unit conversion for explicitly assumed exercise speeds, not observed travel times. */
public final class ExerciseTravelTime {
    private ExerciseTravelTime() {}
    public static double minutes(double metres, double speedKph) {
        if (!Double.isFinite(metres) || metres<0 || !Double.isFinite(speedKph) || speedKph<=0)
            throw new IllegalArgumentException("Finite nonnegative metres and positive speed required");
        double result=metres/1000.0/speedKph*60.0;
        if (!Double.isFinite(result)) throw new IllegalArgumentException("Travel time overflow");
        return result;
    }
}
