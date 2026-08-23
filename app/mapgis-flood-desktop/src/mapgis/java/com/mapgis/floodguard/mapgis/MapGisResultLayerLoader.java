package com.mapgis.floodguard.mapgis;

import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.map.Map;
import com.zondy.mapgis.map.RasterLayer;
import com.zondy.mapgis.pluginengine.IApplication;
import com.zondy.mapgis.pluginengine.plugin.IMapContentsView;
import java.nio.file.Files;
import java.nio.file.Path;

/** Loads an AI-produced raster into the active MapGIS map. Must run on the JavaFX thread. */
public final class MapGisResultLayerLoader {
    public RasterLayer load(IApplication application, Path imagePath, String layerName) {
        if (!Files.isRegularFile(imagePath)) throw new IllegalArgumentException("Result image does not exist: " + imagePath);
        if (!(application.getActiveContentsView() instanceof IMapContentsView mapView)) {
            throw new IllegalStateException("请先激活一个二维地图窗口");
        }
        MapControl control = mapView.getMapControl();
        Map map = control == null ? null : control.getMap();
        if (map == null) throw new IllegalStateException("当前地图窗口没有活动地图");

        RasterLayer layer = new RasterLayer();
        String normalized = imagePath.toAbsolutePath().normalize().toString().replace('\\', '/');
        layer.setURL("file:///" + normalized);
        if (!layer.connectData()) {
            layer.dispose();
            throw new IllegalStateException("MapGIS 无法连接推理结果: " + imagePath);
        }
        layer.setName(layerName);
        map.append(layer);
        control.refreshWnd();
        return layer;
    }
}
