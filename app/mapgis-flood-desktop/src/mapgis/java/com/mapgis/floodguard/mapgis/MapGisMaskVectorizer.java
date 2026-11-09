package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.zondy.mapgis.analysis.rasteranalysis.GridInfo;
import com.zondy.mapgis.analysis.rasteranalysis.RasterToPolygon;
import com.zondy.mapgis.geodatabase.raster.*;
import com.zondy.mapgis.geometry.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.io.IOException;

/** Model patches, NOT building instances. All raster-to-vector work uses native MapGIS. */
public final class MapGisMaskVectorizer {
    public Path export(Path mask, Path destination) throws IOException {
        if (Files.exists(destination)) throw new FileAlreadyExistsException(destination.toString());
        var validatedGrid = new MapGisRasterSpatializer().inspect(mask);
        String wkt = validatedGrid.crs();
        if (!wkt.startsWith("GEOGCS[") || !wkt.contains("AUTHORITY[\"EPSG\",\"4326\"]"))
            throw new IllegalArgumentException("当前GeoJSON导出仅接受EPSG:4326；其他坐标系需先通过MapGIS转换");
        if ((long) validatedGrid.width() * validatedGrid.height() > 1_048_576)
            throw new IllegalArgumentException("当前交互式矢量化限制为1048576像素，请分块处理");
        RasterDataset raster = new RasterDataset();
        RasterBand band = null;
        MemPixelPlane plane = null;
        RasterToPolygon converter = new RasterToPolygon();
        GridInfo info = new GridInfo();
        GeoPolygon[] polygons = null;
        try {
            if (raster.open(mask.toAbsolutePath().toString(), RasterAccess.Read) <= 0 || raster.getBandNum() != 1)
                throw new IllegalArgumentException("需要单波段空间化二值掩膜");
            band = raster.getRasterBand(1);
            plane = band.getPixelPlane(new RasterRectangle(0, 0, raster.getWidth(), raster.getHeight()));
            if (plane == null) throw new IllegalStateException("MapGIS读取掩膜失败");
            long positives = 0;
            double[] pixels = band.getPixels(new RasterRectangle(0, 0, raster.getWidth(), raster.getHeight()));
            if (pixels == null || pixels.length != raster.getWidth() * raster.getHeight())
                throw new IllegalStateException("MapGIS像素读取不完整");
            for (double value : pixels) {
                if (value != 0 && value != 255) throw new IllegalArgumentException("掩膜必须仅包含0与255");
                if (value == 255) positives++;
            }
            info.setWidth(raster.getWidth()); info.setHeight(raster.getHeight());
            info.setOrigin(plane.getOrigin()); info.setCellsize(plane.getCellsize());
            converter.setInput(plane);
            if (positives > 0) {
                polygons = converter.run(info, 0);
                if (polygons == null || polygons.length == 0) throw new IllegalStateException("非空掩膜未返回矢量区");
            }
            var mapper = new ObjectMapper();
            List<Object> features = new ArrayList<>();
            if (polygons != null) for (int i = 0; i < polygons.length; i++) {
                var geometry = mapper.readTree(polygons[i].toGeoJson());
                com.mapgis.floodguard.business.GeoJsonPatchValidator.validate(geometry, validatedGrid);
                features.add(Map.of("type", "Feature", "geometry", geometry,
                        "properties", Map.of("patch_id", i + 1, "source", mask.toAbsolutePath().toString(),
                                "meaning", "predicted_flooded_structure_patch", "verified_damage", false)));
            }
            var collection = new LinkedHashMap<String, Object>();
            collection.put("type", "FeatureCollection"); collection.put("features", features);
            collection.put("engine", "MapGIS RasterToPolygon");
            collection.put("model_patch_count", features.size());
            collection.put("production_ready", false);
            collection.put("warning", "Model patches are NOT building counts, road segments or full flood extent. Spatial overlay and field verification are still required.");
            Files.writeString(destination, mapper.writerWithDefaultPrettyPrinter().writeValueAsString(collection),
                    StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
            return destination;
        } finally {
            if (polygons != null) for (GeoPolygon polygon : polygons) if (polygon != null) polygon.dispose();
            converter.dispose(); info.dispose();
            if (plane != null) plane.dispose();
            if (band != null) band.dispose();
            if (raster.hasOpened()) raster.close(); raster.dispose();
        }
    }
}
