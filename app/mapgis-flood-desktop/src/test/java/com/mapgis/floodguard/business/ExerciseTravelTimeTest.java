package com.mapgis.floodguard.business;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class ExerciseTravelTimeTest {
    @Test void convertsMetresToMinutes() { assertEquals(2,ExerciseTravelTime.minutes(1000,30),1e-12); }
    @Test void allowsZeroLength() { assertEquals(0,ExerciseTravelTime.minutes(0,30)); }
    @Test void rejectsInvalidUnits() {
        assertThrows(IllegalArgumentException.class,()->ExerciseTravelTime.minutes(-1,30));
        assertThrows(IllegalArgumentException.class,()->ExerciseTravelTime.minutes(1,0));
        assertThrows(IllegalArgumentException.class,()->ExerciseTravelTime.minutes(Double.NaN,30));
        assertThrows(IllegalArgumentException.class,()->ExerciseTravelTime.minutes(1,Double.POSITIVE_INFINITY));
    }
}
