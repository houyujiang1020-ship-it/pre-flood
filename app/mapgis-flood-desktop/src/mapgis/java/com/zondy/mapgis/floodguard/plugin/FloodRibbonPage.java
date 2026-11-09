package com.zondy.mapgis.floodguard.plugin;

import com.zondy.mapgis.pluginengine.ui.IRibbonPage;
import com.zondy.mapgis.pluginengine.ui.IRibbonPageGroup;

public final class FloodRibbonPage implements IRibbonPage {
    @Override public String getCategoryKey() { return null; }
    @Override public String getText() { return "洪涝应急"; }
    @Override public boolean isSelected() { return true; }
    @Override public IRibbonPageGroup[] getRibbonPageGroups() { return new IRibbonPageGroup[]{new FloodRibbonGroup()}; }
}
