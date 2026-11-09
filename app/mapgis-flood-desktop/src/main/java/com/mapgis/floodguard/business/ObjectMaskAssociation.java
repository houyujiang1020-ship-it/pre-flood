package com.mapgis.floodguard.business;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Pixel-only association after a MapGIS adapter has rasterized verified reference IDs. */
public final class ObjectMaskAssociation {
    public record Reference(String objectId, String type, int[] pixels) {}
    public record Decision(String objectId, String type, String floodStatus,
                           double normalCoverage, double floodedCoverage) {}
    private ObjectMaskAssociation() {}

    public static List<Decision> associate(int width, int height, boolean[][] masks,
                                           List<Reference> references, double threshold) {
        if (width <= 0 || height <= 0 || (long)width * height > Integer.MAX_VALUE
                || masks == null || masks.length != 4 || references == null
                || !Double.isFinite(threshold) || threshold <= 0 || threshold > 1)
            throw new IllegalArgumentException("Invalid mask grid or decision threshold");
        int size = width * height;
        for (boolean[] mask : masks) if (mask == null || mask.length != size)
            throw new IllegalArgumentException("Mask dimensions differ from reference grid");
        Set<String> ids = new HashSet<>();
        List<Decision> decisions = new ArrayList<>();
        for (Reference reference : references) {
            if (reference == null || reference.objectId() == null || reference.objectId().isBlank()
                    || !ids.add(reference.objectId())
                    || !("building".equals(reference.type()) || "road".equals(reference.type())))
                throw new IllegalArgumentException("Duplicate/missing reference ID or invalid type");
            if (reference.pixels() == null || reference.pixels().length == 0) {
                decisions.add(new Decision(reference.objectId(), reference.type(), "NO_MATCH", 0, 0));
                continue;
            }
            Set<Integer> unique = new HashSet<>();
            int normal = 0, flooded = 0;
            int normalBand = "building".equals(reference.type()) ? 0 : 2;
            for (int pixel : reference.pixels()) {
                if (pixel < 0 || pixel >= size) throw new IllegalArgumentException("Reference pixel outside grid");
                if (!unique.add(pixel)) continue;
                if (masks[normalBand][pixel]) normal++;
                if (masks[normalBand + 1][pixel]) flooded++;
            }
            double normalCoverage = normal / (double)unique.size();
            double floodedCoverage = flooded / (double)unique.size();
            boolean normalHit = normalCoverage >= threshold, floodedHit = floodedCoverage >= threshold;
            String status = normalHit && floodedHit ? "CONFLICT" : floodedHit ? "flooded"
                    : normalHit ? "normal" : "UNKNOWN";
            decisions.add(new Decision(reference.objectId(), reference.type(), status,
                    normalCoverage, floodedCoverage));
        }
        return List.copyOf(decisions);
    }
}
