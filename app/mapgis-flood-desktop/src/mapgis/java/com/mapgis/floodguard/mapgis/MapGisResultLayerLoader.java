package com.mapgis.floodguard.mapgis;

import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.map.Map;
import com.zondy.mapgis.map.RasterLayer;
import com.zondy.mapgis.map.LayerState;
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

        String normalized = imagePath.toAbsolutePath().normalize().toString().replace('\\', '/');
        String url = "file:///" + normalized;
        for (int i = 0; i < map.getLayerCount(); i++) {
            if (map.getLayer(i) instanceof RasterLayer existing && url.equals(existing.getURL())) {
                existing.setState(LayerState.Visible);
                control.restoreWnd(); control.refreshWnd();
                return existing;
            }
        }
        RasterLayer layer = new RasterLayer();
        layer.setURL(url);
        if (!layer.connectData()) {
            layer.dispose();
            throw new IllegalStateException("MapGIS 无法连接推理结果: " + imagePath);
        }
        layer.setName(layerName);
        layer.setState(LayerState.Visible);
        map.append(layer);
        control.restoreWnd();
        control.refreshWnd();
        return layer;
    }

    public void showOnly(IApplication application, RasterLayer selected, RasterLayer... comparison) {
        if (!(application.getActiveContentsView() instanceof IMapContentsView view))
            throw new IllegalStateException("请激活加载结果的二维地图窗口");
        Map map = view.getMapControl().getMap();
        boolean found = false;
        for (int i = 0; i < map.getLayerCount(); i++)
            if (selected.getURL().equals(map.getLayer(i).getURL())) found = true;
        if (!found) throw new IllegalStateException("当前地图不是结果所在地图，请重新加载");
        for (RasterLayer layer : comparison) layer.setState(layer == selected ? LayerState.Visible : LayerState.UnVisible);
        view.getMapControl().restoreWnd(); view.getMapControl().refreshWnd();
    }
}
