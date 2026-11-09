package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.RoadImpedance;
import com.zondy.mapgis.att.Field;
import com.zondy.mapgis.att.Fields;
import com.zondy.mapgis.att.Record;
import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.geodatabase.*;
import com.zondy.mapgis.geodatabase.net.NetCls;
import com.zondy.mapgis.geometry.*;
import com.zondy.mapgis.map.ColorX;
import com.zondy.mapgis.map.LayerState;
import com.zondy.mapgis.map.LineSymbol;
import com.zondy.mapgis.map.SimpleRenderer;
import com.zondy.mapgis.map.VectorLayer;
import com.zondy.mapgis.srs.SRefData;
import java.nio.file.*;
import java.util.*;

/** Four native line layers for before/after paths and hazardous/closed edges. */
public final class MapGisRouteThematicWriter {
    public record Result(Path manifest,List<VectorLayer> layers) {}
    private static final List<String> KINDS=List.of("original","optimized","risk","blocked");
    private static final ObjectMapper JSON=new ObjectMapper();

    public Result write(MapControl control,NetCls network,SRefData sref,EmergencyRoutePlanner.Result routes,
                        Map<Integer,RoadImpedance.Status> statuses,Path directory) throws Exception {
        if (control==null || control.getMap()==null || sref==null) throw new IllegalArgumentException("MapGIS 地图与路网投影必需");
        String name="FG_ROUTE_"+UUID.randomUUID().toString().replace("-","").substring(0,20);
        Server server=null; DataBase db=null; DBFileInfo file=null; FileExtendInfo extend=null; GDBCreateParam create=null;
        Map<String,SFeatureCls> classes=new LinkedHashMap<>(); Map<String,String> urls=new LinkedHashMap<>();
        Map<String,Integer> counts=new LinkedHashMap<>();
        try {
            server=new Server(); require(server.connect("MapGISLocal","",""),"连接 MapGISLocal");
            file=new DBFileInfo(); file.setFilePath(directory.resolve(name+".hdf").toString()); file.setInitSize(10);
            extend=new FileExtendInfo(); extend.setExtendable(true); extend.setExtendMode(FileExtendMode.Size);
            extend.setExtendSize(2); extend.setExtendUnit(FileExtendUnit.Mbyte); file.setExtendInfo(extend);
            create=new GDBCreateParam(); create.setGDBName(name); create.setGDBOwner(name); create.setDataFileInfos(new DBFileInfo[]{file});
            db=server.createGDB(create); if (db==null || !db.hasOpened()) throw new IllegalStateException("MapGIS 路线数据库创建失败");
            int srefId=db.addSRef(sref); require(srefId,"登记空间参考");
            for (String kind:KINDS) {
                SFeatureCls cls=new SFeatureCls(db); Fields fields=fields();
                try { require(cls.create("route_"+kind,GeomType.GeomLin,0,srefId,fields),"创建路线类"); }
                finally { fields.dispose(); }
                classes.put(kind,cls); counts.put(kind,0);
            }
            if (routes!=null) {
                for (int edge:routes.original().edges()) append(classes.get("original"),network,edge,"ORIGINAL",counts,"original");
                for (int edge:routes.optimized().edges()) append(classes.get("optimized"),network,edge,"OPTIMIZED",counts,"optimized");
            }
            for (var item:statuses.entrySet()) {
                if (item.getValue()==RoadImpedance.Status.BLOCKED) append(classes.get("blocked"),network,item.getKey(),"BLOCKED",counts,"blocked");
                else if (item.getValue()==RoadImpedance.Status.FLOODED || item.getValue()==RoadImpedance.Status.HIGH_RISK)
                    append(classes.get("risk"),network,item.getKey(),item.getValue().name(),counts,"risk");
            }
            for (String kind:KINDS) {
                SFeatureCls cls=classes.get(kind);
                if (cls.getObjCount()!=counts.get(kind)) throw new IllegalStateException("路线要素数量不一致："+kind);
                urls.put(kind,cls.getURL());
            }
        } finally {
            for (SFeatureCls cls:classes.values()) cls.close(); if (db!=null) db.close();
            if (create!=null) create.dispose(); if (file!=null) file.dispose(); if (extend!=null) extend.dispose();
            if (server!=null) server.disConnect();
        }
        List<VectorLayer> loaded=new ArrayList<>();
        try {
            for (String kind:KINDS) {
                if (routes==null && (kind.equals("original") || kind.equals("optimized"))) continue;
                VectorLayer layer=new VectorLayer(); layer.setURL(urls.get(kind));
                if (!layer.connectData()) { layer.dispose(); throw new IllegalStateException("路线图层重开失败："+kind); }
                layer.setName(switch(kind) { case "original" -> "原始路线 · 蓝"; case "optimized" -> "优化路线 · 绿";
                    case "risk" -> "风险道路 · 红"; default -> "阻断道路 · 黑"; });
                layer.setState(LayerState.Visible);
                int[] rgb=switch(kind) { case "original" -> new int[]{25,118,210}; case "optimized" -> new int[]{46,125,50};
                    case "risk" -> new int[]{211,47,47}; default -> new int[]{30,30,30}; };
                ColorX color=new ColorX(rgb[0],rgb[1],rgb[2]);
                try { LineSymbol symbol=new LineSymbol(); symbol.setColor(color); symbol.setWidth(kind.equals("optimized")?5:kind.equals("original")?3:4);
                    SimpleRenderer renderer=new SimpleRenderer(); renderer.setSymbol(symbol);
                    layer.setBaseRenderer(renderer); layer.setBaseRendererVisible(true); }
                finally { color.dispose(); }
                if (control.getMap().append(layer)<0) { layer.dispose(); throw new IllegalStateException("添加路线图层失败："+kind); }
                loaded.add(layer);
            }
            control.restoreWnd(); control.refreshWnd();
            Path manifest=directory.resolve(routes==null?"road-closure-manifest.json":"route-thematic-manifest.json");
            Files.writeString(manifest,JSON.writerWithDefaultPrettyPrinter().writeValueAsString(Map.of(
                    "engine","MapGIS","database",directory.resolve(name+".hdf").toString(),
                    "layer_urls",urls,"counts",counts,"colors",Map.of("original","#1976D2","optimized","#2E7D32",
                            "risk","#D32F2F","blocked","#1E1E1E"))),StandardOpenOption.CREATE_NEW);
            return new Result(manifest,List.copyOf(loaded));
        } catch (Exception | LinkageError error) {
            for (VectorLayer layer:loaded) control.getMap().remove(layer); control.refreshWnd(); throw error;
        }
    }
    private static void append(SFeatureCls cls,NetCls network,int edge,String status,Map<String,Integer> counts,String kind) {
        Dots dots=network.getEdgePos(edge); GeoVarLine line=null; Record record=new Record(); Fields schema=cls.getFields();
        try {
            if (dots==null || dots.size()<2) throw new IllegalStateException("网络边缺少几何："+edge);
            line=new GeoVarLine(dots); require(record.setFields(schema),"绑定路线属性");
            require(record.setFieldVal("edge_id",edge),"写入边 ID");
            require(record.setFieldVal("status",status),"写入道路状态");
            require(record.setFieldVal("length_m",MapGisNetworkLength.geometryMetres(network,edge)),"写入长度");
            require(cls.append(line,record,null),"写入路线边"); counts.merge(kind,1,Integer::sum);
        } finally { schema.dispose(); record.dispose(); if (line!=null) line.dispose(); if (dots!=null) dots.dispose(); }
    }
    private static Fields fields() {
        Fields fields=new Fields();
        Field id=new Field(); try { id.setFieldName("edge_id"); id.setFieldType(Field.FieldType.fldLong); require(fields.appendField(id),"创建边 ID 字段"); }
        finally { id.dispose(); }
        Field status=new Field(); try { status.setFieldName("status"); status.setFieldType(Field.FieldType.fldStr); status.setFieldLength((short)20);
            require(fields.appendField(status),"创建状态字段"); } finally { status.dispose(); }
        Field length=new Field(); try { length.setFieldName("length_m"); length.setFieldType(Field.FieldType.fldDouble);
            require(fields.appendField(length),"创建长度字段"); } finally { length.dispose(); }
        return fields;
    }
    private static void require(long result,String task) { if (result<=0) throw new IllegalStateException(task+"失败："+result); }
}
