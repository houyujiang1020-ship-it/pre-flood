package com.mapgis.floodguard.mapgis;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ExerciseLayerTransactionTest {
    @Test void uninitializedNativeHandleIsRejectedBeforeSetUrl() {
        assertThrows(IllegalStateException.class,()->ExerciseLayerTransaction.requireNativeHandle(0));
        assertDoesNotThrow(()->ExerciseLayerTransaction.requireNativeHandle(42));
    }
    private static final List<ExerciseLayerTransaction.Spec> PAIR=List.of(
            new ExerciseLayerTransaction.Spec("gdbp://building","buildings"),
            new ExerciseLayerTransaction.Spec("gdbp://road","roads"));
    private static final class FakeStore implements ExerciseLayerTransaction.Store<String> {
        final Set<String> layers=new LinkedHashSet<>();
        int adds, removes;
        boolean failRoad;
        public boolean contains(String url) { return layers.contains(url); }
        public String add(ExerciseLayerTransaction.Spec spec) {
            if (failRoad && spec.url().endsWith("road")) throw new IllegalStateException("road connection failed");
            adds++; layers.add(spec.url()); return spec.url();
        }
        public void remove(String layer) { removes++; layers.remove(layer); }
        public void refresh() {}
    }
    @Test void repeatedLoadDoesNotDuplicateNativeLayerUrls() {
        FakeStore store=new FakeStore();
        ExerciseLayerTransaction.run(PAIR,store);
        ExerciseLayerTransaction.run(PAIR,store);
        assertEquals(Set.of("gdbp://building","gdbp://road"),store.layers);
        assertEquals(2,store.adds);
    }
    @Test void failedSecondLayerRollsBackOnlyNewlyAddedLayer() {
        FakeStore store=new FakeStore(); store.failRoad=true;
        assertThrows(IllegalStateException.class,()->ExerciseLayerTransaction.run(PAIR,store));
        assertTrue(store.layers.isEmpty());
        assertEquals(1,store.removes);
    }
    @Test void rollbackPreservesLayerAlreadyPresentBeforeImport() {
        FakeStore store=new FakeStore(); store.layers.add("gdbp://building"); store.failRoad=true;
        assertThrows(IllegalStateException.class,()->ExerciseLayerTransaction.run(PAIR,store));
        assertEquals(Set.of("gdbp://building"),store.layers);
        assertEquals(0,store.removes);
    }
}
