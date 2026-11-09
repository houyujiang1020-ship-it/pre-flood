package com.mapgis.floodguard.business;

import java.nio.file.Path;

/** Stage 8 numerical cross-check over persisted native MapGIS result evidence. */
public final class FinalValidator {
    public static void main(String[] args) throws Exception {
        if (args.length!=3) throw new IllegalArgumentException("用法：FinalValidator damage.json risk.json route.json");
        Path output=new ResultValidator().validate(Path.of(args[0]),Path.of(args[1]),Path.of(args[2]),
                Path.of("final_validation.json"));
        System.out.println(output.toAbsolutePath());
    }
}
