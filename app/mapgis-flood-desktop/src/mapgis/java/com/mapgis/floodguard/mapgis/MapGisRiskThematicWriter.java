package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.zondy.mapgis.att.Field;
import com.zondy.mapgis.att.Fields;
import com.zondy.mapgis.att.Record;
import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.geodatabase.*;
import com.zondy.mapgis.geometry.Geometry;
import com.zondy.mapgis.geometry.GeomType;
import com.zondy.mapgis.map.ColorX;
import com.zondy.mapgis.map.FillSymbol;
import com.zondy.mapgis.map.LayerState;
import com.zondy.mapgis.map.SimpleRenderer;
import com.zondy.mapgis.map.VectorLayer;
import java.nio.file.*;
import java.util.*;

/** Persists complete and partial risk zones as native MapGIS polygon feature classes. */
public final class MapGisRiskThematicWriter {
    public record Result(Path manifest, List<VectorLayer> layers) {}
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final List<String> LEVELS = List.of("LOW","MEDIUM","HIGH","PARTIAL");

    public Result write(MapControl control, FloodRiskAssessment.Inputs input,
                        FloodRiskAssessment.Result assessment) throws Exception {
        if (control==null || control.getMap()==null) throw new IllegalStateException("MapGIS 地图未就绪");
        String base="FG_RISK_"+UUID.randomUUID().toString().replace("-","").substring(0,20);
        Server server=null; DataBase db=null; DBFileInfo file=null; FileExtendInfo extend=null;
        GDBCreateParam create=null;
        Map<String,SFeatureCls> classes=new LinkedHashMap<>();
        Map<String,String> urls=new LinkedHashMap<>();
        Map<String,Integer> counts=new LinkedHashMap<>();
        try {
            server=new Server(); require(server.connect("MapGISLocal","",""),"连接 MapGISLocal");
            file=new DBFileInfo(); file.setFilePath(assessment.directory().resolve(base+".hdf").toString()); file.setInitSize(10);
            extend=new FileExtendInfo(); extend.setExtendable(true); extend.setExtendMode(FileExtendMode.Size);
            extend.setExtendSize(2); extend.setExtendUnit(FileExtendUnit.Mbyte); file.setExtendInfo(extend);
            create=new GDBCreateParam(); create.setGDBName(base); create.setGDBOwner(base); create.setDataFileInfos(new DBFileInfo[]{file});
            db=server.createGDB(create);
            if (db==null || !db.hasOpened()) throw new IllegalStateException("MapGIS 风险数据库创建失败");
            int srefId=db.addSRef(input.areas().getSrefInfo()); require(srefId,"登记空间参考");
            for (String level:LEVELS) {
                SFeatureCls cls=new SFeatureCls(db); Fields schema=fields("PARTIAL".equals(level));
                try { require(cls.create("risk_"+level.toLowerCase(Locale.ROOT),GeomType.GeomReg,0,srefId,schema),"创建风险类"); }
                finally { schema.dispose(); }
                classes.put(level,cls); counts.put(level,0);
            }
            Map<String,FloodRiskAssessment.AreaResult> byId=new HashMap<>();
            for (var item:assessment.areas()) byId.put(item.areaId(),item);
            SFeatureCls source=(SFeatureCls)input.areas().getData();
            QueryDef query=new QueryDef(); RecordSet rows=null;
            try {
                rows=source.query(query); if (rows==null) throw new IllegalStateException("MapGIS 行政区读取失败");
                int count=rows.getCount(); if (count>0) rows.moveFirst();
                for (int i=0;i<count;i++) {
                    Geometry geometry=rows.getGeometry(); Record original=rows.getAtt();
                    try {
                        Object areaId=original.getFieldVal("area_id");
                        var result=byId.get(String.valueOf(areaId).trim());
                        if (result==null) throw new IllegalStateException("行政区结果与源对象不一致："+areaId);
                        {
                            String level=result.riskLevel()==null?"PARTIAL":result.riskLevel();
                            SFeatureCls cls=classes.get(level);
                            Record record=new Record(); Fields schema=cls.getFields();
                            try {
                                require(record.setFields(schema),"绑定风险属性");
                                put(record,"area_id",result.areaId()); put(record,"area_name",result.area());
                                put(record,"risk_level",level);
                                if (result.riskScore()==null) {
                                    put(record,"status","PARTIAL");
                                } else {
                                    put(record,"risk_score",result.riskScore());
                                    put(record,"building_risk",result.buildingRisk()); put(record,"population_risk",result.populationRisk());
                                    put(record,"road_risk",result.roadRisk()); put(record,"resource_risk",result.resourceDistanceRisk());
                                    put(record,"affected_population",result.affectedPopulation());
                                    put(record,"damaged_buildings",result.damagedBuildings());
                                    put(record,"blocked_roads",result.blockedRoads());
                                    put(record,"blocked_road_m",result.blockedRoadMetres());
                                }
                                require(cls.append(geometry,record,null),"写入风险区域");
                                counts.merge(level,1,Integer::sum);
                            } finally { schema.dispose(); record.dispose(); }
                        }
                    } finally { if (geometry!=null) geometry.dispose(); if (original!=null) original.dispose(); }
                    if (i+1<count) rows.moveNext();
                }
            } finally { if (rows!=null) rows.dispose(); query.dispose(); }
            for (String level:LEVELS) {
                SFeatureCls cls=classes.get(level);
                if (cls.getObjCount()!=counts.get(level)) throw new IllegalStateException("MapGIS 风险对象数不一致："+level);
                urls.put(level,cls.getURL());
            }
        } finally {
            for (SFeatureCls cls:classes.values()) cls.close();
            if (db!=null) db.close(); if (create!=null) create.dispose();
            if (file!=null) file.dispose(); if (extend!=null) extend.dispose(); if (server!=null) server.disConnect();
        }
        List<VectorLayer> loaded=new ArrayList<>();
        try {
            for (String level:LEVELS) {
                VectorLayer layer=new VectorLayer(); layer.setURL(urls.get(level));
                if (!layer.connectData()) { layer.dispose(); throw new IllegalStateException("风险图层重开失败："+level); }
                layer.setName("洪涝风险分区 · "+level); layer.setState(LayerState.Visible);
                ColorX color=switch(level) { case "LOW" -> new ColorX(46,125,50); case "MEDIUM" -> new ColorX(255,193,7);
                    case "HIGH" -> new ColorX(211,47,47); default -> new ColorX(158,158,158); };
                try { FillSymbol symbol=new FillSymbol(); symbol.setColor(color); SimpleRenderer renderer=new SimpleRenderer();
                    renderer.setSymbol(symbol); layer.setBaseRenderer(renderer); layer.setBaseRendererVisible(true); }
                finally { color.dispose(); }
                if (control.getMap().append(layer)<0) { layer.dispose(); throw new IllegalStateException("风险图层加载失败"); }
                loaded.add(layer);
            }
            control.restoreWnd(); control.refreshWnd();
            Path manifest=assessment.directory().resolve("risk-thematic-manifest.json");
            Map<String,Object> data=new LinkedHashMap<>(); data.put("status","native_mapgis_layers_loaded");
            data.put("database",assessment.directory().resolve(base+".hdf").toString());
            data.put("source_report",assessment.reportJson().toString()); data.put("layer_urls",urls);
            data.put("counts",counts); data.put("colors",Map.of("LOW","#2E7D32","MEDIUM","#FFC107","HIGH","#D32F2F","PARTIAL","#9E9E9E"));
            data.put("partial_areas",assessment.areas().stream().filter(a->a.riskScore()==null).map(FloodRiskAssessment.AreaResult::areaId).toList());
            Files.writeString(manifest,JSON.writerWithDefaultPrettyPrinter().writeValueAsString(data),StandardOpenOption.CREATE_NEW);
            return new Result(manifest,List.copyOf(loaded));
        } catch (Exception | LinkageError error) {
            for (VectorLayer layer:loaded) control.getMap().remove(layer);
            control.refreshWnd(); throw error;
        }
    }
    private static Fields fields(boolean partial) {
        Fields schema=new Fields();
        add(schema,"area_id",Field.FieldType.fldStr,80); add(schema,"area_name",Field.FieldType.fldStr,80);
        add(schema,"risk_level",Field.FieldType.fldStr,16);
        if (partial) { add(schema,"status",Field.FieldType.fldStr,16); return schema; }
        for (String name:List.of("risk_score","building_risk","population_risk","road_risk","resource_risk","affected_population","blocked_road_m"))
            add(schema,name,Field.FieldType.fldDouble,0);
        add(schema,"damaged_buildings",Field.FieldType.fldLong,0); add(schema,"blocked_roads",Field.FieldType.fldLong,0);
        return schema;
    }
    private static void add(Fields schema,String name,Field.FieldType type,int length) {
        Field field=new Field(); try { field.setFieldName(name); field.setFieldType(type);
            if (length>0) field.setFieldLength((short)length); require(schema.appendField(field),"添加字段 "+name); }
        finally { field.dispose(); }
    }
    private static void put(Record record,String key,Object value) { require(record.setFieldVal(key,value),"写入字段 "+key); }
    private static void require(long value,String task) { if (value<=0) throw new IllegalStateException(task+"失败："+value); }
}
