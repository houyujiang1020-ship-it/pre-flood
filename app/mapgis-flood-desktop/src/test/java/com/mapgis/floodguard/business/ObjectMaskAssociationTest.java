package com.mapgis.floodguard.business;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class ObjectMaskAssociationTest {
    @Test void sharedPredictedPixelsCanAssociateWithMultipleStableObjects() {
        boolean[][] masks = new boolean[4][4];
        masks[1][0] = masks[1][1] = true;
        var decisions = ObjectMaskAssociation.associate(2,2,masks,List.of(
                new ObjectMaskAssociation.Reference("b1","building",new int[]{0,1}),
                new ObjectMaskAssociation.Reference("b2","building",new int[]{1,2})),.5);
        assertEquals("flooded",decisions.get(0).floodStatus());
        assertEquals("flooded",decisions.get(1).floodStatus());
        assertEquals(1.0,decisions.get(0).floodedCoverage());
        assertEquals(.5,decisions.get(1).floodedCoverage());
    }

    @Test void independentSigmoidsPreserveConflictAndRoadFloodingIsNotClosure() {
        boolean[][] masks = new boolean[4][4];
        masks[0][0] = masks[1][0] = masks[3][1] = true;
        var decisions = ObjectMaskAssociation.associate(2,2,masks,List.of(
                new ObjectMaskAssociation.Reference("b","building",new int[]{0}),
                new ObjectMaskAssociation.Reference("r","road",new int[]{1})),.5);
        assertEquals("CONFLICT",decisions.get(0).floodStatus());
        assertEquals("flooded",decisions.get(1).floodStatus());
        assertNotEquals("blocked",decisions.get(1).floodStatus());
    }

    @Test void emptyAndInvalidReferencesCannotBecomeSuccessfulObjects() {
        boolean[][] masks = new boolean[4][4];
        assertEquals("NO_MATCH",ObjectMaskAssociation.associate(2,2,masks,List.of(
                new ObjectMaskAssociation.Reference("b","building",new int[]{})),.5).get(0).floodStatus());
        assertThrows(IllegalArgumentException.class,()->ObjectMaskAssociation.associate(2,2,masks,List.of(
                new ObjectMaskAssociation.Reference("same","building",new int[]{0}),
                new ObjectMaskAssociation.Reference("same","road",new int[]{1})),.5));
        assertThrows(IllegalArgumentException.class,()->ObjectMaskAssociation.associate(2,2,masks,List.of(
                new ObjectMaskAssociation.Reference("bad","road",new int[]{4})),.5));
    }
}
