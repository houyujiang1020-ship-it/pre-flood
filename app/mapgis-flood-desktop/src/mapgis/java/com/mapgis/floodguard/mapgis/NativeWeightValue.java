package com.mapgis.floodguard.mapgis;

import com.zondy.mapgis.common.ObjectRef;

/** Strict adapter for SDK versions returning numeric weights as Number, numeric text, or ObjectRef. */
final class NativeWeightValue {
    static double asDouble(Object value) {
        Object current=value;
        for (int depth=0; depth<2 && current instanceof ObjectRef ref; depth++) current=ref.getValue();
        double result;
        if (current instanceof Number number) result=number.doubleValue();
        else if (current instanceof CharSequence text) {
            String normalized=text.toString().trim();
            if (normalized.isEmpty() || normalized.length()>64) throw unsupported(value);
            try { result=Double.parseDouble(normalized); }
            catch (NumberFormatException error) { throw unsupported(value); }
        } else throw unsupported(value);
        if (!Double.isFinite(result)) throw unsupported(value);
        return result;
    }
    static String type(Object value) { return value==null ? "null" : value.getClass().getName(); }
    private static IllegalStateException unsupported(Object value) {
        return new IllegalStateException("Registered length weight has unsupported value type: "+type(value));
    }
}
