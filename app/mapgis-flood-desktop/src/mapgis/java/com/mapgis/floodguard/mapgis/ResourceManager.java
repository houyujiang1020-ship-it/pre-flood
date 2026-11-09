package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.zondy.mapgis.att.Field;
import com.zondy.mapgis.att.Fields;
import com.zondy.mapgis.att.Record;
import com.zondy.mapgis.controls.MapControl;
import com.zondy.mapgis.geodatabase.*;
import com.zondy.mapgis.geodatabase.net.NetCls;
import com.zondy.mapgis.geometry.*;
import com.zondy.mapgis.map.*;
import com.zondy.mapgis.srs.SRefData;
import java.nio.file.*;
import java.util.*;
import java.util.Map;

/** Editable rescue resources persisted as native MapGIS point feature classes. */
public final class ResourceManager {
    public enum Kind { VEHICLE, MEDICAL, SHELTER }
    public record Resource(String id,Kind kind,String name,String type,String status,
                           int capacity,int current,double x,double y,int nodeId) {
        public Resource {
            if (id==null || id.isBlank() || kind==null || name==null || name.isBlank()
                    || type==null || type.isBlank() || status==null || status.isBlank()
                    || capacity<0 || current<0 || current>capacity
                    || !Double.isFinite(x) || !Double.isFinite(y) || nodeId<=0)
                throw new IllegalArgumentException("资源编号、坐标、容量和 MapGIS 网络节点必须有效");
        }
    }
    private final MapControl control;
    private final EnumMap<Kind,VectorLayer> layers=new EnumMap<>(Kind.class);
    private final Path databasePath;
    private static final ObjectMapper JSON=new ObjectMapper();

    private ResourceManager(MapControl control,Path databasePath) {
        this.control=control; this.databasePath=databasePath;
    }

    public ResourceManager(MapControl control,SRefData sref,Path evidenceRoot) throws Exception {
        if (control==null || control.getMap()==null || sref==null) throw new IllegalArgumentException("MapGIS 地图和投影必需");
        this.control=control;
        Path directory=Files.createDirectories(evidenceRoot.resolve("resources-"+UUID.randomUUID()));
        String dbName="FG_RESOURCE_"+UUID.randomUUID().toString().replace("-","").substring(0,20);
        databasePath=directory.resolve(dbName+".hdf");
        Server server=null; DataBase db=null; DBFileInfo file=null; FileExtendInfo extend=null; GDBCreateParam create=null;
        EnumMap<Kind,String> urls=new EnumMap<>(Kind.class);
        try {
            server=new Server(); require(server.connect("MapGISLocal","",""),"连接 MapGISLocal");
            file=new DBFileInfo(); file.setFilePath(databasePath.toString()); file.setInitSize(10);
            extend=new FileExtendInfo(); extend.setExtendable(true); extend.setExtendMode(FileExtendMode.Size);
            extend.setExtendSize(2); extend.setExtendUnit(FileExtendUnit.Mbyte); file.setExtendInfo(extend);
            create=new GDBCreateParam(); create.setGDBName(dbName); create.setGDBOwner(dbName); create.setDataFileInfos(new DBFileInfo[]{file});
            db=server.createGDB(create); if (db==null || !db.hasOpened()) throw new IllegalStateException("MapGIS 资源库创建失败");
            int srefId=db.addSRef(sref); require(srefId,"登记空间参考");
            for (Kind kind:Kind.values()) {
                SFeatureCls cls=new SFeatureCls(db); Fields schema=fields();
                try { require(cls.create("resource_"+kind.name().toLowerCase(Locale.ROOT),GeomType.GeomPnt,0,srefId,schema),"创建资源类");
                    urls.put(kind,cls.getURL()); }
                finally { schema.dispose(); cls.close(); }
            }
        } finally {
            if (db!=null) db.close(); if (create!=null) create.dispose(); if (file!=null) file.dispose();
            if (extend!=null) extend.dispose(); if (server!=null) server.disConnect();
        }
        try {
            for (Kind kind:Kind.values()) {
                VectorLayer layer=new VectorLayer(); layer.setURL(urls.get(kind));
                if (!layer.connectData()) { layer.dispose(); throw new IllegalStateException("资源图层重开失败："+kind); }
                layer.setName(switch(kind) { case VEHICLE -> "救援车辆"; case MEDICAL -> "医疗资源"; case SHELTER -> "避难点"; });
                layer.setState(LayerState.Visible); style(layer,kind);
                if (control.getMap().append(layer)<0) { layer.dispose(); throw new IllegalStateException("资源图层添加失败"); }
                layers.put(kind,layer);
            }
            control.refreshWnd();
            Map<String,String> saved=new LinkedHashMap<>();
            for (var entry:urls.entrySet()) saved.put(entry.getKey().name(),entry.getValue());
            Files.writeString(manifestPath(),JSON.writerWithDefaultPrettyPrinter().writeValueAsString(
                    java.util.Map.of("engine","MapGIS","database",databasePath.toString(),"layer_urls",saved)),
                    StandardOpenOption.CREATE_NEW);
        } catch (Exception | LinkageError error) {
            for (VectorLayer layer:layers.values()) control.getMap().remove(layer);
            control.refreshWnd(); throw error;
        }
    }
    public Path databasePath() { return databasePath; }
    public Path manifestPath() { return databasePath.getParent().resolve("resource-manifest.json"); }
    public static ResourceManager openExisting(MapControl control,Path manifest,SRefData networkSref) throws Exception {
        return openExisting(control,manifest,networkSref,null);
    }
    public static ResourceManager openExisting(MapControl control,Path manifest,SRefData networkSref,
                                               NetCls network) throws Exception {
        var data=JSON.readTree(manifest.toFile());
        if (!"MapGIS".equals(data.path("engine").asText()) || !data.path("layer_urls").isObject())
            throw new IllegalArgumentException("不是 FloodGuard MapGIS 资源清单");
        Path database=Path.of(data.path("database").asText());
        if (!Files.isRegularFile(database)) throw new IllegalArgumentException("MapGIS 资源 HDF 不存在："+database);
        ResourceManager manager=new ResourceManager(control,database);
        List<VectorLayer> newlyAttached=new ArrayList<>();
        try {
            for (Kind kind:Kind.values()) {
                String url=data.path("layer_urls").path(kind.name()).asText();
                if (url.isBlank()) throw new IllegalArgumentException("资源清单缺少图层："+kind);
                VectorLayer layer=null;
                for (int i=0;i<control.getMap().getLayerCount();i++) {
                    var candidate=control.getMap().getLayer(i);
                    if (candidate instanceof VectorLayer vector && url.equals(vector.getURL())) { layer=vector; break; }
                }
                if (layer==null) {
                    layer=new VectorLayer(); layer.setURL(url);
                    if (!layer.connectData()) { layer.dispose(); throw new IllegalStateException("MapGIS 资源图层连接失败："+kind); }
                    layer.setName(switch(kind) { case VEHICLE -> "救援车辆"; case MEDICAL -> "医疗资源"; case SHELTER -> "避难点"; });
                    layer.setState(LayerState.Visible);
                    if (control.getMap().append(layer)<0) { layer.dispose(); throw new IllegalStateException("资源图层添加失败："+kind); }
                    newlyAttached.add(layer);
                }
                if (layer.getSrefInfo()==null || networkSref==null
                        || !layer.getSrefInfo().toWkt().equals(networkSref.toWkt()))
                    throw new IllegalArgumentException("资源库与当前路网空间参考不一致："+kind);
                style(layer,kind);
                manager.layers.put(kind,layer);
            }
            control.refreshWnd();
            List<Resource> loaded=manager.list();
            if (network!=null) for (Resource resource:loaded) {
                Dot node=new Dot();
                if (!network.hasOpened() || network.getNodeInfo(resource.nodeId())==null
                        || network.getNodPos(resource.nodeId(),node)<=0
                        || Math.hypot(resource.x()-node.getX(),resource.y()-node.getY())>25)
                    throw new IllegalArgumentException("资源节点绑定不属于当前路网或距离超过 25 m："+resource.id());
            }
            return manager;
        } catch (Exception | LinkageError error) {
            for (VectorLayer layer:newlyAttached) control.getMap().remove(layer);
            control.refreshWnd(); throw error;
        }
    }
    public Collection<VectorLayer> layers() { return List.copyOf(layers.values()); }
    public void add(Resource resource) {
        if (find(resource.id())!=null) throw new IllegalArgumentException("资源编号已存在："+resource.id());
        SFeatureCls cls=featureClass(resource.kind()); GeoPoint point=new GeoPoint();
        Record record=record(cls,resource);
        try { require(point.set(resource.x(),resource.y(),0),"设置资源坐标");
            require(cls.append(point,record,null),"写入资源点"); control.refreshWnd(); }
        finally { point.dispose(); record.dispose(); }
    }
    public void update(Resource resource) {
        Located old=find(resource.id()); if (old==null) throw new IllegalArgumentException("资源不存在："+resource.id());
        if (old.resource().kind()!=resource.kind()) throw new IllegalArgumentException("资源类别不能修改；请删除后重新添加");
        SFeatureCls cls=featureClass(resource.kind()); GeoPoint point=new GeoPoint(); Record record=record(cls,resource);
        try { require(point.set(resource.x(),resource.y(),0),"设置资源坐标");
            require(cls.update(old.oid(),point,record,null),"更新资源点"); control.refreshWnd(); }
        finally { point.dispose(); record.dispose(); }
    }
    public void delete(String id) {
        Located found=find(id); if (found==null) throw new IllegalArgumentException("资源不存在："+id);
        if (!featureClass(found.resource().kind()).delete(found.oid())) throw new IllegalStateException("MapGIS 删除资源点失败");
        control.refreshWnd();
    }
    public List<Resource> list() {
        List<Resource> out=new ArrayList<>(); for (Kind kind:Kind.values()) scan(kind,(oid,resource)->out.add(resource));
        return List.copyOf(out);
    }
    public record Located(long oid,Resource resource) {}
    public Located find(String id) {
        if (id==null || id.isBlank()) return null;
        List<Located> hits=new ArrayList<>();
        for (Kind kind:Kind.values()) scan(kind,(oid,resource)->{ if (resource.id().equals(id)) hits.add(new Located(oid,resource)); });
        if (hits.size()>1) throw new IllegalStateException("MapGIS 资源编号重复："+id);
        return hits.isEmpty()?null:hits.get(0);
    }
    private interface Visitor { void accept(long oid,Resource resource); }
    private void scan(Kind kind,Visitor visitor) {
        SFeatureCls cls=featureClass(kind); QueryDef query=new QueryDef(); RecordSet rows=null;
        try {
            rows=cls.query(query); if (rows==null) throw new IllegalStateException("MapGIS 资源查询失败");
            int count=rows.getCount(); if (count<0 || count>100_000) throw new IllegalStateException("资源数量超出限制");
            if (count>0) rows.moveFirst();
            for (int i=0;i<count;i++) {
                Record record=rows.getAtt();
                if (record==null) throw new IllegalStateException("资源属性缺失");
                try {
                    Resource resource=new Resource(str(record,"resource_id"),kind,str(record,"name"),str(record,"type"),
                            str(record,"status"),integer(record,"capacity"),integer(record,"current"),
                            number(record,"x"),number(record,"y"),integer(record,"node_id"));
                    visitor.accept(rows.getID(),resource);
                } finally { record.dispose(); }
                if (i+1<count) rows.moveNext();
            }
        } finally { if (rows!=null) rows.dispose(); query.dispose(); }
    }
    private SFeatureCls featureClass(Kind kind) {
        VectorLayer layer=layers.get(kind);
        if (layer==null || !(layer.getData() instanceof SFeatureCls cls) || !cls.hasOpened())
            throw new IllegalStateException("MapGIS 资源图层未连接："+kind);
        return cls;
    }
    private static Record record(SFeatureCls cls,Resource resource) {
        Record record=new Record(); Fields fields=cls.getFields();
        try { require(record.setFields(fields),"绑定资源属性");
            put(record,"resource_id",resource.id()); put(record,"name",resource.name()); put(record,"type",resource.type());
            put(record,"status",resource.status()); put(record,"capacity",resource.capacity()); put(record,"current",resource.current());
            put(record,"x",resource.x()); put(record,"y",resource.y()); put(record,"node_id",resource.nodeId());
            return record;
        } catch (RuntimeException error) { record.dispose(); throw error; }
        finally { fields.dispose(); }
    }
    private static Fields fields() {
        Fields fields=new Fields();
        for (String name:List.of("resource_id","name","type","status")) add(fields,name,Field.FieldType.fldStr,80);
        for (String name:List.of("capacity","current","node_id")) add(fields,name,Field.FieldType.fldLong,0);
        add(fields,"x",Field.FieldType.fldDouble,0); add(fields,"y",Field.FieldType.fldDouble,0);
        return fields;
    }
    private static void add(Fields fields,String name,Field.FieldType type,int length) {
        Field field=new Field(); try { field.setFieldName(name); field.setFieldType(type);
            if (length>0) field.setFieldLength((short)length); require(fields.appendField(field),"添加资源字段"); }
        finally { field.dispose(); }
    }
    private static String str(Record r,String key) { Object value=r.getFieldVal(key); return value==null?"":value.toString(); }
    private static int integer(Record r,String key) { Object value=r.getFieldVal(key); if (!(value instanceof Number n)) throw new IllegalStateException("资源字段缺失："+key); return n.intValue(); }
    private static double number(Record r,String key) { Object value=r.getFieldVal(key); if (!(value instanceof Number n)) throw new IllegalStateException("资源字段缺失："+key); return n.doubleValue(); }
    private static void put(Record r,String key,Object value) { require(r.setFieldVal(key,value),"写入资源属性 "+key); }
    private static void require(long result,String action) { if (result<=0) throw new IllegalStateException(action+"失败："+result); }
    private static void style(VectorLayer layer,Kind kind) {
        ColorX color=switch(kind) { case VEHICLE -> new ColorX(255,140,0); case MEDICAL -> new ColorX(211,47,47);
            case SHELTER -> new ColorX(30,136,229); };
        try {
            MarkerSymbol symbol=new MarkerSymbol(); symbol.setColor(color); symbol.setSize(20);
            SvgMarkerSymbolLayer marker=new SvgMarkerSymbolLayer();
            marker.setData(switch(kind) {
                case VEHICLE -> "<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><rect x='3' y='10' width='18' height='12' rx='2' fill='#FF8C00'/><path d='M21 14h5l4 5v3h-9z' fill='#FF8C00'/><circle cx='9' cy='24' r='3' fill='#263238'/><circle cx='25' cy='24' r='3' fill='#263238'/></svg>";
                case MEDICAL -> "<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><circle cx='16' cy='16' r='15' fill='#D32F2F'/><path d='M13 5h6v8h8v6h-8v8h-6v-8H5v-6h8z' fill='white'/></svg>";
                case SHELTER -> "<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><path d='M16 31C8 21 3 17 3 12a13 13 0 0 1 26 0c0 5-5 9-13 19z' fill='#1E88E5'/><circle cx='16' cy='12' r='5' fill='white'/></svg>";
            });
            symbol.addLayer(marker);
            if (symbol.getLayerCount()<=0) throw new IllegalStateException("MapGIS 资源符号设置失败");
            SimpleRenderer renderer=new SimpleRenderer(); renderer.setSymbol(symbol);
            layer.setBaseRenderer(renderer); layer.setBaseRendererVisible(true);
        } finally { color.dispose(); }
    }
}
