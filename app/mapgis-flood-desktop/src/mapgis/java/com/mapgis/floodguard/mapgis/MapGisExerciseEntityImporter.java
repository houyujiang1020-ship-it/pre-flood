package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.*;
import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.geodatabase.*;
import com.zondy.mapgis.geometry.*;
import com.zondy.mapgis.map.*;
import com.zondy.mapgis.pluginengine.IApplication;
import com.zondy.mapgis.pluginengine.plugin.IMapContentsView;
import com.zondy.mapgis.srs.SRefData;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Imports only manifest-verified fictional exercise entities into a new local HDF. */
final class MapGisExerciseEntityImporter {
    private static final String WGS84="GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563]],PRIMEM[\"Greenwich\",0],UNIT[\"degree\",0.0174532925199433],AUTHORITY[\"EPSG\",\"4326\"]]";
    private static final java.util.Map<String,Result> COMPLETED = new HashMap<>();
    record Result(String database, String buildingsUrl, String roadsUrl, int buildings, int roads) {}

    Result importAndLoad(IApplication application, Path source) throws Exception {
        if (!(application.getActiveContentsView() instanceof IMapContentsView view))
            throw new IllegalStateException("请先激活二维地图");
        ObjectMapper json=new ObjectMapper();
        JsonNode manifest=json.readTree(source.resolve("manifest.json").toFile());
        JsonNode buildingJson=verified(json,manifest,source,"buildings.geojson");
        JsonNode roadJson=verified(json,manifest,source,"roads.geojson");
        requireCollection(buildingJson,"building"); requireCollection(roadJson,"road");
        String key=source.toRealPath()+":"+manifest.path("files").path("buildings.geojson").asText()
                +":"+manifest.path("files").path("roads.geojson").asText();
        Result previous=COMPLETED.get(key);
        if (previous!=null) {
            loadBoth(view.getMapControl(),previous);
            return previous;
        }
        Path output=Files.createDirectory(source.resolve("entities-mapgis-"+UUID.randomUUID()));
        String name="FE_"+UUID.randomUUID().toString().replace("-","").substring(0,24);
        Server server=null; DataBase db=null; SFeatureCls buildings=null, roads=null;
        GDBCreateParam createParam=null; DBFileInfo dataFile=null; FileExtendInfo extension=null; SRefData sref=null;
        String stage="initialize", url="", target="Server";
        try {
            stage="connect_server";
            server=new Server(); require(server.connect("MapGISLocal","",""),"连接 MapGISLocal");
            dataFile=new DBFileInfo(); dataFile.setFilePath(output.resolve(name+".hdf").toString()); dataFile.setInitSize(10);
            extension=new FileExtendInfo(); extension.setExtendable(true); extension.setExtendMode(FileExtendMode.Size);
            extension.setExtendSize(2); extension.setExtendUnit(FileExtendUnit.Mbyte); extension.setMaxFileSize(0); dataFile.setExtendInfo(extension);
            createParam=new GDBCreateParam(); createParam.setGDBName(name); createParam.setGDBOwner(name); createParam.setDataFileInfos(new DBFileInfo[]{dataFile});
            stage="create_database"; target="DataBase";
            db=server.createGDB(createParam); if(db==null || !db.hasOpened()) throw new IllegalStateException("创建实体数据库失败");
            sref=SRefData.fromWkt(WGS84,false); if(sref==null) throw new IllegalStateException("无法解析 WGS84");
            int srefId=db.addSRef(sref); require(srefId,"登记 WGS84");
            stage="create_buildings"; target="SFeatureCls";
            buildings=create(db,"exercise_buildings",GeomType.GeomReg,srefId);
            stage="create_roads";
            roads=create(db,"exercise_roads_wgs84",GeomType.GeomLin,srefId);
            stage="append_buildings";
            int buildingCount=append(buildings,buildingJson,GeomType.GeomReg);
            stage="append_roads";
            int roadCount=append(roads,roadJson,GeomType.GeomLin);
            String buildingUrl=buildings.getURL(),roadUrl=roads.getURL();
            if (buildingUrl==null || buildingUrl.isBlank() || roadUrl==null || roadUrl.isBlank())
                throw new IllegalStateException("原生要素类 URL 为空");
            Result result=new Result(name,buildingUrl,roadUrl,buildingCount,roadCount);
            stage="load_layers"; target="VectorLayer(SFclsLayer)"; url=buildingUrl+" | "+roadUrl;
            loadBoth(view.getMapControl(),result);
            COMPLETED.put(key,result);
            return result;
        } catch (Exception | LinkageError error) {
            throw new IllegalStateException("MapGIS 演练实体导入失败: stage="+stage+", method=MapGisExerciseEntityImporter.importAndLoad"
                    +", target="+target+", url="+url+", feature_handles_open="
                    +(buildings!=null && buildings.hasOpened())+"/"+(roads!=null && roads.hasOpened())
                    +", database_open="+(db!=null && db.hasOpened())+", thread="+Thread.currentThread().getName()
                    +", case="+source.toAbsolutePath(),error);
        } finally {
            if(buildings!=null && buildings.hasOpened()) buildings.close();
            if(roads!=null && roads.hasOpened()) roads.close();
            if(db!=null && db.hasOpened()) db.close();
            if(sref!=null) sref.dispose(); if(createParam!=null) createParam.dispose(); if(dataFile!=null) dataFile.dispose();
            if(extension!=null) extension.dispose(); if(server!=null) server.disConnect();
        }
    }
    private static JsonNode verified(ObjectMapper json,JsonNode manifest,Path source,String file) throws Exception {
        byte[] bytes=Files.readAllBytes(source.resolve(file));
        if(bytes.length>10_000_000) throw new IllegalArgumentException(file+" exceeds exercise limit");
        String digest=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        if(!digest.equals(manifest.path("files").path(file).asText())) throw new IllegalArgumentException("Manifest mismatch: "+file);
        return json.readTree(bytes);
    }
    private static void requireCollection(JsonNode value,String kind) {
        if(!"FeatureCollection".equals(value.path("type").asText()) || !value.path("features").isArray() || value.path("features").isEmpty())
            throw new IllegalArgumentException("No "+kind+" features");
    }
    private static SFeatureCls create(DataBase db,String name,GeomType type,int srefId) {
        SFeatureCls cls=new SFeatureCls(db); com.zondy.mapgis.att.Fields fields=null;
        boolean created=false;
        try {
            fields=new com.zondy.mapgis.att.Fields();
            require(cls.create(name,type,0,srefId,fields),"创建 "+name);
            created=true; return cls;
        } finally {
            if (fields!=null) fields.dispose();
            if (!created && cls.getHandle()!=0) cls.close();
        }
    }
    private static int append(SFeatureCls cls,JsonNode collection,GeomType expected) {
        int count=0;
        for(JsonNode feature:collection.path("features")) {
            String geometryType=feature.path("geometry").path("type").asText();
            if ((expected==GeomType.GeomReg && !"Polygon".equals(geometryType))
                    || (expected==GeomType.GeomLin && !"LineString".equals(geometryType)))
                throw new IllegalArgumentException("演练实体几何类型不符: expected="+expected+", actual="+geometryType);
            Geometry geometry=Geometry.fromGeoJson(feature.path("geometry").toString());
            try {
                if(geometry==null) throw new IllegalArgumentException("无法读取 GeoJSON 几何");
                require(cls.append(geometry,null,null),"写入实体"); count++;
            } finally { if(geometry!=null) geometry.dispose(); }
        }
        if(cls.getObjCount()!=count) throw new IllegalStateException("实体写入数量不一致");
        return count;
    }
    private static void loadBoth(MapControl control,Result result) {
        if(control==null || control.getMap()==null) throw new IllegalStateException("当前地图不可用");
        ExerciseLayerTransaction.run(List.of(
                new ExerciseLayerTransaction.Spec(result.buildingsUrl(),"exercise_buildings"),
                new ExerciseLayerTransaction.Spec(result.roadsUrl(),"exercise_roads_wgs84")),
                new ExerciseLayerTransaction.Store<VectorLayer>() {
                    public boolean contains(String url) {
                        for (int i=0;i<control.getMap().getLayerCount();i++)
                            if (url.equals(control.getMap().getLayer(i).getURL())) return true;
                        return false;
                    }
                    public VectorLayer add(ExerciseLayerTransaction.Spec spec) { return load(control,spec.url(),spec.name()); }
                    public void remove(VectorLayer layer) {
                        if (!control.getMap().remove(layer)) throw new IllegalStateException("无法回滚半初始化图层: "+layer.getURL());
                    }
                    public void refresh() { control.restoreWnd(); control.refreshWnd(); }
                });
    }
    private static VectorLayer load(MapControl control,String url,String name) {
        // The SDK's no-arg VectorLayer constructor leaves getHandle()==0.
        VectorLayer layer=new VectorLayer(VectorLayerType.SFclsLayer);
        boolean attached=false;
        String phase="create_native_layer";
        try {
            ExerciseLayerTransaction.requireNativeHandle(layer.getHandle());
            phase="setURL";
            if(!layer.setURL(url)) throw new IllegalStateException("MapGIS 设置实体 URL 失败: "+url);
            phase="connectData";
            if(!layer.connectData() || !(layer.getData() instanceof SFeatureCls))
                throw new IllegalStateException("MapGIS 无法连接原生面/线要素类: "+url);
            layer.setName(name); layer.setState(LayerState.Visible);
            phase="append_to_map";
            if (control.getMap().append(layer)<0) throw new IllegalStateException("MapGIS 添加实体图层失败: "+url);
            attached=true; return layer;
        } catch (RuntimeException | LinkageError error) {
            long handle=layer.getHandle();
            if (!attached && handle!=0) {
                try { layer.dispose(); }
                catch (RuntimeException | LinkageError cleanup) { error.addSuppressed(cleanup); }
            }
            throw new IllegalStateException("MapGisExerciseEntityImporter.load: phase="+phase
                    +", target=VectorLayer(SFclsLayer), url="+url+", native_handle="+handle
                    +", disposed="+(!attached && handle!=0)+", thread="+Thread.currentThread().getName(),error);
        }
    }
    private static void require(long value,String operation) { if(value<=0) throw new IllegalStateException(operation+"失败: "+value); }
}
