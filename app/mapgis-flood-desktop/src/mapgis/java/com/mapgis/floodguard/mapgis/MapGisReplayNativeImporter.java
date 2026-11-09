package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mapgis.floodguard.business.DamagePrediction;
import com.zondy.mapgis.att.Field;
import com.zondy.mapgis.att.Fields;
import com.zondy.mapgis.att.Record;
import com.zondy.mapgis.geodatabase.*;
import com.zondy.mapgis.geometry.GeomType;
import com.zondy.mapgis.geometry.Geometry;
import com.zondy.mapgis.srs.SRefData;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Imports only hash-verified P0-07 exercise geometry into a new MapGISLocal HDF. */
public final class MapGisReplayNativeImporter {
    private static final ObjectMapper JSON = new ObjectMapper();
    private record Layer(String file,String name,GeomType geometry,List<String> fields) {}
    private static final List<Layer> LAYERS=List.of(
            new Layer("buildings.geojson","replay_buildings",GeomType.GeomReg,List.of("source_id","source_file")),
            new Layer("roads.geojson","replay_roads",GeomType.GeomLin,List.of("source_id","source_file")),
            new Layer("population.geojson","replay_population",GeomType.GeomReg,
                    List.of("source_id","grid_id","population","population_unit","population_source")),
            new Layer("administrative.geojson","replay_administrative",GeomType.GeomReg,
                    List.of("source_id","area_id","area_name","resource_risk_status")),
            new Layer("flood_extent.geojson","replay_flood_extent",GeomType.GeomReg,
                    List.of("source_id","flood_kind","flood_source","observation_status")));

    public static void main(String[] args) throws Exception {
        if (args.length!=2) throw new IllegalArgumentException("source-directory new-output-directory required");
        System.out.println(importCase(Path.of(args[0]),Path.of(args[1])));
    }

    public static Path importCase(Path source,Path output) throws Exception {
        source=source.toAbsolutePath().normalize(); output=output.toAbsolutePath().normalize();
        JsonNode manifest=JSON.readTree(source.resolve("source-manifest.json").toFile());
        if (!"REPLAY_SIMULATION".equals(manifest.path("mode").asText()) || manifest.path("ready").asBoolean(true)
                || !"EPSG:32632".equals(manifest.path("crs").asText()))
            throw new IllegalArgumentException("仅允许尚未验收的 EPSG:32632 模拟 REPLAY 输入");
        Map<Layer,JsonNode> inputs=new LinkedHashMap<>();
        for (Layer layer:LAYERS) {
            Path file=source.resolve(layer.file());
            byte[] bytes=Files.readAllBytes(file);
            String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
            if (!hash.equals(manifest.path("files").path(layer.file()).path("sha256").asText()))
                throw new IllegalArgumentException("源文件哈希不一致："+file);
            JsonNode value=JSON.readTree(bytes);
            if (!"FeatureCollection".equals(value.path("type").asText()) || !value.path("features").isArray()
                    || value.path("features").isEmpty() ||
                    !"EPSG:32632".equals(value.path("crs").path("properties").path("name").asText()))
                throw new IllegalArgumentException("投影或要素集无效："+file);
            inputs.put(layer,value);
        }
        Path predictionPath=source.resolve("flood_prediction.json");
        byte[] predictionBytes=Files.readAllBytes(predictionPath);
        String predictionHash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(predictionBytes));
        if (!predictionHash.equals(manifest.path("files").path("flood_prediction.json").path("sha256").asText()))
            throw new IllegalArgumentException("对象预测文件哈希不一致："+predictionPath);
        DamagePrediction.read(predictionPath);
        JsonNode prediction=JSON.readTree(predictionBytes);
        String wkt=prediction.path("crs_wkt").asText();
        if (!wkt.contains("32632") || !wkt.contains("metre"))
            throw new IllegalArgumentException("对象预测缺少 EPSG:32632 米制投影");
        Map<String,JsonNode> sourceGeometries=new LinkedHashMap<>();
        Map<String,String> sourceTypes=new LinkedHashMap<>();
        for (var entry:inputs.entrySet()) {
            String type=switch(entry.getKey().name()) {
                case "replay_buildings" -> "building"; case "replay_roads" -> "road"; default -> null;
            };
            if (type==null) continue;
            for (JsonNode feature:entry.getValue().path("features")) {
                String id=feature.path("id").asText();
                if (id.isBlank() || sourceGeometries.putIfAbsent(id,feature.path("geometry"))!=null)
                    throw new IllegalArgumentException("参考对象 ID 缺失或重复："+id);
                sourceTypes.put(id,type);
            }
        }
        Set<String> predictedIds=new HashSet<>();
        for (JsonNode object:prediction.path("objects")) {
            String id=object.path("object_id").asText();
            if (!predictedIds.add(id) || !object.path("type").asText().equals(sourceTypes.get(id))
                    || !object.path("geometry").equals(sourceGeometries.get(id)))
                throw new IllegalArgumentException("预测对象与模拟参考几何或类型不一致："+id);
        }
        if (!predictedIds.equals(sourceGeometries.keySet()))
            throw new IllegalArgumentException("预测对象 ID 与模拟参考对象不一致");
        Files.createDirectory(output);
        String name="FG_REPLAY_"+UUID.randomUUID().toString().replace("-","").substring(0,18);
        Path databaseFile=output.resolve(name+".hdf");
        Map<String,Object> evidence=new LinkedHashMap<>();
        evidence.put("simulation_only",true); evidence.put("native_import_verified",false);
        evidence.put("source_manifest",source.resolve("source-manifest.json").toString());
        evidence.put("database_file",databaseFile.toString());
        Map<String,Object> layers=new LinkedHashMap<>(); evidence.put("layers",layers);
        Server server=null; DataBase db=null; DBFileInfo file=null; FileExtendInfo extend=null;
        GDBCreateParam create=null; SRefData sref=null;
        try {
            evidence.put("stage","connect_server");
            server=new Server(); require(server.connect("MapGISLocal","",""),"连接 MapGISLocal");
            if (server.getDBID(name)>0) throw new IllegalStateException("数据库名称已存在："+name);
            file=new DBFileInfo(); file.setFilePath(databaseFile.toString()); file.setInitSize(10);
            extend=new FileExtendInfo(); extend.setExtendable(true); extend.setExtendMode(FileExtendMode.Size);
            extend.setExtendSize(2); extend.setExtendUnit(FileExtendUnit.Mbyte); file.setExtendInfo(extend);
            create=new GDBCreateParam(); create.setGDBName(name); create.setGDBOwner(name);
            create.setDataFileInfos(new DBFileInfo[]{file});
            evidence.put("stage","create_database");
            db=server.createGDB(create);
            if (db==null || !db.hasOpened()) throw new IllegalStateException("MapGIS 创建模拟 HDF 失败");
            sref=SRefData.fromWkt(wkt,false);
            if (sref==null) throw new IllegalStateException("MapGIS 无法解析 EPSG:32632 WKT");
            int srefId=db.addSRef(sref); require(srefId,"登记米制投影");
            evidence.put("database_url",db.getURL()); evidence.put("sref_id",srefId);
            for (var item:inputs.entrySet()) {
                Layer spec=item.getKey(); JsonNode collection=item.getValue();
                evidence.put("stage","import_"+spec.name());
                SFeatureCls cls=new SFeatureCls(db); Fields schema=fields(spec);
                try {
                    require(cls.create(spec.name(),spec.geometry(),0,srefId,schema),"创建 "+spec.name());
                    Map<String,Long> ids=new LinkedHashMap<>();
                    for (JsonNode feature:collection.path("features")) {
                        String id=feature.path("id").asText();
                        if (id.isBlank() || ids.containsKey(id)) throw new IllegalArgumentException("对象 ID 缺失或重复："+id);
                        Geometry geometry=Geometry.fromGeoJson(feature.path("geometry").toString());
                        Record record=new Record();
                        try {
                            if (geometry==null) throw new IllegalArgumentException("几何无效："+id);
                            require(record.setFields(schema),"绑定字段");
                            JsonNode props=feature.path("properties");
                            for (String fieldName:spec.fields()) {
                                JsonNode value=props.path(fieldName);
                                if (value.isMissingNode() || value.isNull()) throw new IllegalArgumentException(id+" 缺少 "+fieldName);
                                Object fieldValue=fieldName.equals("population")?value.asDouble():value.asText();
                                require(record.setFieldVal(fieldName,fieldValue),"写入 "+fieldName);
                            }
                            long oid=cls.append(geometry,record,null); require(oid,"写入 "+id); ids.put(id,oid);
                        } finally { record.dispose(); if (geometry!=null) geometry.dispose(); }
                    }
                    if (cls.getObjCount()!=ids.size()) throw new IllegalStateException("原生对象数不一致："+spec.name());
                    String url=cls.getURL(); cls.close();
                    SFeatureCls reader=new SFeatureCls();
                    try {
                        require(reader.openByURL(url),"重开 "+spec.name());
                        if (reader.getObjCount()!=ids.size() || reader.getsrID()!=srefId)
                            throw new IllegalStateException("重开后数量或投影不一致："+spec.name());
                    } finally { reader.close(); }
                    layers.put(spec.name(),Map.of("url",url,"count",ids.size(),"source_to_native_oid",ids,
                            "fields",spec.fields(),"source_sha256",manifest.path("files").path(spec.file()).path("sha256").asText()));
                } finally { schema.dispose(); cls.close(); }
            }
            evidence.put("stage","verified"); evidence.put("native_import_verified",true);
            return output.resolve("native-import.json");
        } catch (Exception | LinkageError error) { evidence.put("error",error.toString()); throw error; }
        finally {
            try { Files.writeString(output.resolve("native-import.json"),
                    JSON.writerWithDefaultPrettyPrinter().writeValueAsString(evidence),StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE_NEW); }
            finally {
                if (db!=null) db.close(); if (sref!=null) sref.dispose();
                if (create!=null) create.dispose(); if (file!=null) file.dispose();
                if (extend!=null) extend.dispose(); if (server!=null) server.disConnect();
            }
        }
    }

    private static Fields fields(Layer layer) {
        Fields fields=new Fields();
        for (String name:layer.fields()) {
            Field field=new Field();
            try {
                field.setFieldName(name);
                field.setFieldType(name.equals("population")?Field.FieldType.fldDouble:Field.FieldType.fldStr);
                if (!name.equals("population")) field.setFieldLength((short)240);
                require(fields.appendField(field),"添加字段 "+name);
            } finally { field.dispose(); }
        }
        return fields;
    }
    private static void require(long code,String action) {
        if (code<=0) throw new IllegalStateException(action+"失败："+code);
    }
}
