package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.DamagePrediction;
import com.zondy.mapgis.att.Field;
import com.zondy.mapgis.att.Fields;
import com.zondy.mapgis.att.Record;
import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.geodatabase.*;
import com.zondy.mapgis.geometry.*;
import com.zondy.mapgis.map.ColorX;
import com.zondy.mapgis.map.FillSymbol;
import com.zondy.mapgis.map.LineSymbol;
import com.zondy.mapgis.map.SimpleRenderer;
import com.zondy.mapgis.map.VectorLayer;
import com.zondy.mapgis.map.LayerState;
import com.zondy.mapgis.srs.SRefData;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Four native MapGIS feature classes, each with an explicit official SDK renderer. */
public final class MapGisDamageThematicImporter {
    public record Result(Path directory, Path manifest, List<VectorLayer> layers, Map<String,Integer> counts) {}
    private static final ObjectMapper JSON = new ObjectMapper();

    public Result importAndLoad(MapControl control, Path input, Path evidenceRoot) throws Exception {
        if (control == null || control.getMap() == null) throw new IllegalStateException("MapGIS 地图未就绪");
        DamagePrediction.Dataset data = DamagePrediction.read(input);
        Path directory = Files.createDirectories(evidenceRoot).resolve("damage-" + UUID.randomUUID());
        Files.createDirectory(directory);
        String name = "FG_" + UUID.randomUUID().toString().replace("-", "").substring(0,24);
        Server server = null; DataBase database = null; SRefData sref = null;
        DBFileInfo dbFile = null; FileExtendInfo extend = null; GDBCreateParam create = null;
        EnumMap<DamagePrediction.ClassId,SFeatureCls> classes = new EnumMap<>(DamagePrediction.ClassId.class);
        EnumMap<DamagePrediction.ClassId,Integer> counts = new EnumMap<>(DamagePrediction.ClassId.class);
        EnumMap<DamagePrediction.ClassId,String> urls = new EnumMap<>(DamagePrediction.ClassId.class);
        try {
            server = new Server();
            require(server.connect("MapGISLocal","",""), "连接 MapGISLocal");
            dbFile = new DBFileInfo(); dbFile.setFilePath(directory.resolve(name + ".hdf").toString()); dbFile.setInitSize(10);
            extend = new FileExtendInfo(); extend.setExtendable(true); extend.setExtendMode(FileExtendMode.Size);
            extend.setExtendSize(2); extend.setExtendUnit(FileExtendUnit.Mbyte); extend.setMaxFileSize(0);
            dbFile.setExtendInfo(extend);
            create = new GDBCreateParam(); create.setGDBName(name); create.setGDBOwner(name);
            create.setDataFileInfos(new DBFileInfo[]{dbFile});
            database = server.createGDB(create);
            if (database == null || !database.hasOpened()) throw new IllegalStateException("MapGIS 灾损数据库创建失败");
            sref = SRefData.fromWkt(data.crsWkt(), false);
            if (sref == null) throw new IllegalArgumentException("MapGIS 无法解析 crs_wkt");
            int srefId = database.addSRef(sref); require(srefId,"登记空间参考");
            for (DamagePrediction.ClassId category : DamagePrediction.ClassId.values()) {
                SFeatureCls features = new SFeatureCls(database);
                Fields fields = fields();
                try {
                    GeomType type = category.name().startsWith("BUILDING") ? GeomType.GeomReg : GeomType.GeomLin;
                    require(features.create(category.name().toLowerCase(Locale.ROOT),type,0,srefId,fields),"创建"+category);
                } finally { fields.dispose(); }
                classes.put(category,features); counts.put(category,0);
            }
            for (DamagePrediction.Feature feature : data.features()) {
                Geometry geometry = Geometry.fromGeoJson(feature.geometry().toString());
                if (geometry == null) throw new IllegalArgumentException("MapGIS 无法解析对象几何："+feature.objectId());
                try {
                    boolean building = feature.category().name().startsWith("BUILDING");
                    if (building && !(geometry instanceof GeoPolygon) || !building && !(geometry instanceof GeoLine))
                        throw new IllegalArgumentException("对象几何与分类不匹配："+feature.objectId());
                    double measure = building ? ((GeoPolygon)geometry).calArea() : ((GeoLine)geometry).calLength();
                    if (!Double.isFinite(measure) || measure <= 0) throw new IllegalArgumentException("对象面积/长度无效："+feature.objectId());
                    Rect rect = geometry.calRect();
                    if (rect == null || !rect.isValid()) throw new IllegalArgumentException("对象范围无效："+feature.objectId());
                    Record record = new Record(); Fields schema = classes.get(feature.category()).getFields();
                    try {
                        require(record.setFields(schema),"绑定对象属性");
                        put(record,"object_id",feature.objectId());
                        put(record,"object_type",building ? "building" : "road");
                        put(record,"flood_status",feature.floodStatus());
                        put(record,"damage_probability",feature.damageProbability());
                        put(record,"severity",DamagePrediction.severity(feature));
                        put(record,"area_m2",building ? measure : 0.0);
                        put(record,"length_m",building ? 0.0 : measure);
                        put(record,"x",(rect.getXMin()+rect.getXMax())/2);
                        put(record,"y",(rect.getYMin()+rect.getYMax())/2);
                        long oid = classes.get(feature.category()).append(geometry,record,null);
                        require(oid,"写入对象 "+feature.objectId());
                        counts.merge(feature.category(),1,Integer::sum);
                    } finally { schema.dispose(); record.dispose(); }
                } finally { geometry.dispose(); }
            }
            for (var entry : classes.entrySet()) {
                SFeatureCls features = entry.getValue();
                if (features.getObjCount() != counts.get(entry.getKey()))
                    throw new IllegalStateException("MapGIS 对象数量不一致："+entry.getKey());
                urls.put(entry.getKey(),features.getURL());
            }
        } finally {
            for (SFeatureCls featureClass : classes.values()) featureClass.close();
            if (database != null) database.close();
            if (sref != null) sref.dispose();
            if (create != null) create.dispose(); if (dbFile != null) dbFile.dispose();
            if (extend != null) extend.dispose(); if (server != null) server.disConnect();
        }
        List<VectorLayer> loaded = new ArrayList<>();
        try {
            for (DamagePrediction.ClassId category : DamagePrediction.ClassId.values()) {
                VectorLayer layer = new VectorLayer(); layer.setURL(urls.get(category));
                if (!layer.connectData()) { layer.dispose(); throw new IllegalStateException("MapGIS 无法重开专题类："+category); }
                layer.setName(label(category)); layer.setState(LayerState.Visible);
                applyRenderer(layer,category);
                if (control.getMap().append(layer) < 0) { layer.dispose(); throw new IllegalStateException("专题图层添加失败："+category); }
                loaded.add(layer);
            }
            control.restoreWnd(); control.refreshWnd();
            LinkedHashMap<String,Object> report = new LinkedHashMap<>();
            report.put("status","native_mapgis_layers_loaded"); report.put("source",input.toAbsolutePath().toString());
            report.put("source_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(input))));
            report.put("crs_wkt",data.crsWkt()); report.put("database",directory.resolve(name+".hdf").toString());
            report.put("feature_count",data.features().size()); report.put("counts",counts);
            report.put("layer_urls",urls); report.put("area_unit","m2"); report.put("coordinate_meaning","geometry bounding-box centre in declared CRS");
            report.put("classification_rule","explicit flood_status; road flooded does not imply blocked");
            report.put("colors",Map.of("building_flooded","#D32F2F","building_normal","#2E7D32","road_flooded","#FF9800","road_blocked","#000000","road_normal","#757575"));
            report.put("field_verification",false); report.put("model_accuracy_verified",false);
            Path manifest = directory.resolve("thematic-manifest.json");
            Files.writeString(manifest,JSON.writerWithDefaultPrettyPrinter().writeValueAsString(report),StandardOpenOption.CREATE_NEW);
            return new Result(directory,manifest,List.copyOf(loaded),counts.entrySet().stream().collect(
                    java.util.stream.Collectors.toMap(e -> e.getKey().name(),Map.Entry::getValue)));
        } catch (Exception | LinkageError error) {
            for (VectorLayer layer : loaded) control.getMap().remove(layer);
            control.refreshWnd();
            throw error;
        }
    }
    private static Fields fields() {
        Fields fields = new Fields();
        add(fields,"object_id",Field.FieldType.fldStr,80); add(fields,"object_type",Field.FieldType.fldStr,16);
        add(fields,"flood_status",Field.FieldType.fldStr,20); add(fields,"damage_probability",Field.FieldType.fldDouble,0);
        add(fields,"severity",Field.FieldType.fldStr,16); add(fields,"area_m2",Field.FieldType.fldDouble,0);
        add(fields,"length_m",Field.FieldType.fldDouble,0); add(fields,"x",Field.FieldType.fldDouble,0);
        add(fields,"y",Field.FieldType.fldDouble,0);
        return fields;
    }
    private static void add(Fields fields,String name,Field.FieldType type,int length) {
        Field field = new Field();
        try { field.setFieldName(name); field.setFieldType(type); if (length>0) field.setFieldLength((short)length);
            require(fields.appendField(field),"添加字段 "+name); }
        finally { field.dispose(); }
    }
    private static void put(Record record,String key,Object value) { require(record.setFieldVal(key,value),"写入字段 "+key); }
    private static void applyRenderer(VectorLayer layer,DamagePrediction.ClassId category) {
        boolean building = category.name().startsWith("BUILDING");
        boolean affected = category == DamagePrediction.ClassId.BUILDING_FLOODED || category == DamagePrediction.ClassId.ROAD_FLOODED || category == DamagePrediction.ClassId.ROAD_BLOCKED;
        int[] rgb = building ? (affected ? new int[]{211,47,47} : new int[]{46,125,50})
                : (category == DamagePrediction.ClassId.ROAD_BLOCKED ? new int[]{0,0,0}
                   : category == DamagePrediction.ClassId.ROAD_FLOODED ? new int[]{255,152,0} : new int[]{117,117,117});
        ColorX color = new ColorX(rgb[0],rgb[1],rgb[2]);
        SimpleRenderer renderer = new SimpleRenderer();
        try {
            if (building) { FillSymbol symbol = new FillSymbol(); symbol.setColor(color); renderer.setSymbol(symbol); }
            else { LineSymbol symbol = new LineSymbol(); symbol.setColor(color); symbol.setWidth(affected ? 4.0 : 1.5); renderer.setSymbol(symbol); }
            layer.setBaseRenderer(renderer); layer.setBaseRendererVisible(true);
        } finally { color.dispose(); }
    }
    private static String label(DamagePrediction.ClassId category) {
        return switch(category) {
            case BUILDING_NORMAL -> "灾损专题 · 未受淹建筑（绿）";
            case BUILDING_FLOODED -> "灾损专题 · 受淹建筑（红）";
            case ROAD_NORMAL -> "灾损专题 · 正常道路（灰）";
            case ROAD_FLOODED -> "灾损专题 · 预测受淹道路（橙）";
            case ROAD_BLOCKED -> "灾损专题 · 核查阻断道路（黑）";
        };
    }
    private static void require(long code,String action) { if (code <= 0) throw new IllegalStateException(action+"失败："+code); }
}

