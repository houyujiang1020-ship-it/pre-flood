package com.mapgis.floodguard.mapgis;

import com.zondy.mapgis.pluginengine.ui.IItem;
import com.zondy.mapgis.pluginengine.ui.IRibbonPageGroup;
import com.zondy.mapgis.pluginengine.ui.Item;

public final class FloodRibbonGroup implements IRibbonPageGroup {
    @Override public String getText() { return "智能解译"; }
    @Override public IItem[] getIItems() { return new IItem[]{new Item(FloodInferenceCommand.class.getName())}; }
}
