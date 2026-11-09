package com.mapgis.floodguard.mapgis;

import java.util.ArrayList;
import java.util.List;

/** Adds missing layers as one operation; a partial addition is rolled back. */
final class ExerciseLayerTransaction {
    static void requireNativeHandle(long handle) {
        if (handle==0) throw new IllegalStateException("MapGIS VectorLayer 原生句柄未初始化；禁止调用 setURL");
    }
    record Spec(String url, String name) {}
    interface Store<T> {
        boolean contains(String url);
        T add(Spec spec);
        void remove(T layer);
        void refresh();
    }
    static <T> void run(List<Spec> specs, Store<T> store) {
        List<T> added=new ArrayList<>();
        try {
            for (Spec spec:specs) if (!store.contains(spec.url())) added.add(store.add(spec));
            store.refresh();
        } catch (RuntimeException | LinkageError error) {
            for (int i=added.size()-1;i>=0;i--) {
                try { store.remove(added.get(i)); }
                catch (RuntimeException | LinkageError cleanup) { error.addSuppressed(cleanup); }
            }
            try { store.refresh(); }
            catch (RuntimeException | LinkageError cleanup) { error.addSuppressed(cleanup); }
            throw error;
        }
    }
}
