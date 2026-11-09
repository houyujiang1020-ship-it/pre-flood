package com.mapgis.floodguard.mapgis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.zondy.mapgis.geodatabase.*;
import com.zondy.mapgis.geodatabase.net.*;
import com.zondy.mapgis.geometry.*;
import com.zondy.mapgis.srs.SRefData;
import java.nio.file.*;
import java.util.*;

/** Creates only a new exercise database. Never modifies an existing operational network. */
public final class MapGisExerciseNetworkBuilder {
    private static final String WGS84="GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563]],PRIMEM[\"Greenwich\",0],UNIT[\"degree\",0.0174532925199433],AUTHORITY[\"EPSG\",\"4326\"]]";
    private static final String UTM32="PROJCS[\"WGS 84 / UTM zone 32N\","+WGS84+",PROJECTION[\"Transverse_Mercator\"],PARAMETER[\"latitude_of_origin\",0],PARAMETER[\"central_meridian\",9],PARAMETER[\"scale_factor\",0.9996],PARAMETER[\"false_easting\",500000],PARAMETER[\"false_northing\",0],UNIT[\"metre\",1],AUTHORITY[\"EPSG\",\"32632\"]]";

    public static void main(String[] args) throws Exception {
        if (args.length!=2) throw new IllegalArgumentException("source-directory new-output-directory required");
        build(Path.of(args[0]),Path.of(args[1]));
    }
    public static Path build(Path source, Path output) throws Exception {
        ObjectMapper json=new ObjectMapper();
        var manifest=json.readTree(source.resolve("manifest.json").toFile());
        Path input=source.resolve("roads.geojson");
        if (Files.size(input)>10_000_000) throw new IllegalArgumentException("Road input exceeds exercise limit");
        byte[] bytes=Files.readAllBytes(input);
        String digest=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
        if (!digest.equals(manifest.path("files").path("roads.geojson").asText())) throw new IllegalArgumentException("Road file differs from source manifest");
        var collection=json.readTree(bytes);
        if (!"FeatureCollection".equals(collection.path("type").asText()) || collection.path("features").isEmpty())
            throw new IllegalArgumentException("No official road features");
        output=Files.createDirectory(output.toAbsolutePath());
        Map<String,Object> evidence=new LinkedHashMap<>();
        evidence.put("scenario_only",true); evidence.put("native_network_created",false);
        evidence.put("dispatch_ready",false); evidence.put("source_sha256",digest);
        Server server=null; DataBase db=null; SFeatureCls roads=null; NetCls net=null;
        NetFeatureList features=null; NetWeightList weights=null; NetWeightFldList fields=null;
        SRefData geographic=null, projected=null;
        GDBCreateParam createParam=null; DBFileInfo dataFile=null; FileExtendInfo extension=null;
        try {
            evidence.put("stage","connect_server");
            server=new Server();
            require(server.connect("MapGISLocal","",""),"连接本地MapGIS数据源");
            String name=com.mapgis.floodguard.business.ExerciseDatabaseName.from(UUID.randomUUID());
            evidence.put("database_name",name); evidence.put("server_type",server.getConnectType().toString());
            if (server.getConnectType()!=com.zondy.mapgis.geodatabase.config.ConnectType.Local)
                throw new IllegalStateException("MapGISLocal不是预期的本地HDF数据源");
            if (server.getDBID(name)>0) throw new IllegalStateException("数据库名称已存在，拒绝覆盖");
            Path databaseFile=output.resolve(name+".hdf");
            evidence.put("database_file",databaseFile.toString()); evidence.put("stage","create_database");
            // Mirror the official CreateGDBDialog's local-file parameters; no SQL-style log file.
            dataFile=new DBFileInfo(); dataFile.setFilePath(databaseFile.toString()); dataFile.setInitSize(10);
            extension=new FileExtendInfo(); extension.setExtendable(true); extension.setExtendMode(FileExtendMode.Size);
            extension.setExtendSize(2); extension.setExtendUnit(FileExtendUnit.Mbyte); extension.setMaxFileSize(0);
            dataFile.setExtendInfo(extension);
            createParam=new GDBCreateParam(); createParam.setGDBName(name); createParam.setGDBOwner(name);
            createParam.setDataFileInfos(new DBFileInfo[]{dataFile});
            db=server.createGDB(createParam);
            if (db==null) throw new IllegalStateException("MapGIS创建演练数据库返回空对象，名称="+name+"，文件="+databaseFile);
            if (!Boolean.TRUE.equals(db.hasOpened())) throw new IllegalStateException("MapGIS返回数据库但未打开，名称="+name);
            evidence.put("stage","import_roads");
            evidence.put("database_url",db.getURL());
            geographic=SRefData.fromWkt(WGS84,false); projected=SRefData.fromWkt(UTM32,false);
            if (geographic==null || projected==null) throw new IllegalStateException("MapGIS无法解析坐标系");
            int geographicId=db.addSRef(geographic); require(geographicId,"登记WGS84");
            evidence.put("stage","create_road_class");
            evidence.put("road_class_name","exercise_roads"); evidence.put("road_sref_id",geographicId);
            roads=new SFeatureCls(db);
            // The two-argument overload accepts a full URL, NOT a name in the bound database.
            // Match official CreateDataDialog: name, geometry type, dataset ID, SRef ID, fields.
            com.zondy.mapgis.att.Fields roadFields=new com.zondy.mapgis.att.Fields();
            com.zondy.mapgis.att.Field lengthField=new com.zondy.mapgis.att.Field();
            int roadClassId;
            try {
                // Same standard length field as official GISDefaultValues.getDefaultFieldLength().
                lengthField.setFieldName("mpLength");
                lengthField.setFieldType(com.zondy.mapgis.att.Field.FieldType.fldDouble);
                lengthField.setFieldLength((short)15);
                roadFields.appendField(lengthField);
                roadClassId=roads.create("exercise_roads",GeomType.GeomLin,0,geographicId,roadFields);
            } finally { roadFields.dispose(); lengthField.dispose(); }
            evidence.put("road_create_return",roadClassId);
            require(roadClassId,"创建道路线类");
            if (!roads.hasOpened()) throw new IllegalStateException("已创建道路线类，但类未打开");
            evidence.put("road_class_id",roadClassId); evidence.put("roads_url",roads.getURL());
            evidence.put("stage","append_roads");
            Map<String,Long> sourceIds=new LinkedHashMap<>();
            for (var feature:collection.path("features")) {
                String id=feature.path("id").asText();
                if (id.isBlank() || sourceIds.containsKey(id)) throw new IllegalArgumentException("Duplicate/missing road identity");
                Geometry geometry=Geometry.fromGeoJson(feature.path("geometry").toString());
                if (geometry==null) throw new IllegalArgumentException("Invalid road geometry");
                try {
                    evidence.put("current_source_road",id);
                    long fid=roads.append(geometry,null,null); require(fid,"写入真实道路 "+id); sourceIds.put(id,fid);
                    evidence.put("imported_road_count",sourceIds.size());
                }
                finally { geometry.dispose(); }
            }
            if (roads.getObjCount()!=sourceIds.size()) throw new IllegalStateException("导入道路线数量不一致");
            evidence.put("source_feature_ids",sourceIds);
            evidence.put("stage","project_roads");
            int projectionResult=roads.projTrans(projected);
            evidence.put("projection_return",projectionResult);
            require(projectionResult,"MapGIS道路投影转换");
            evidence.put("stage","populate_native_length_field");
            var persistedFields=roads.getFields();
            try {
                short lengthIndex=persistedFields.getFieldIndex("mpLength");
                if (lengthIndex<0) throw new IllegalStateException("标准长度字段缺失");
                int lengthResult=roads.lengthToField(false,lengthIndex);
                evidence.put("length_to_field_return",lengthResult);
                require(lengthResult,"MapGIS计算投影平面长度");
            } finally { persistedFields.dispose(); }
            Map<String,Double> sourceLengths=new LinkedHashMap<>();
            evidence.put("source_length_metres",sourceLengths);
            for (var entry:sourceIds.entrySet()) {
                var attributes=roads.getAtt(entry.getValue());
                Geometry shape=roads.getGeometry(entry.getValue());
                try {
                    if (attributes==null || !(shape instanceof GeoLine line)) throw new IllegalStateException("长度校验缺少原生数据");
                    Object value=attributes.getFieldVal("mpLength");
                    if (!(value instanceof Number length)) throw new IllegalStateException("长度属性不是数值");
                    com.mapgis.floodguard.business.NetworkLengthCheck.verify(length.doubleValue(),line.calLength());
                    sourceLengths.put(entry.getKey(),length.doubleValue());
                } finally { if(attributes!=null) attributes.dispose(); if(shape!=null) shape.dispose(); }
            }
            evidence.put("stage","verify_persisted_roads");
            // Check the persisted class, not just the still-open writer's state.
            roads.close();
            require(roads.open(roadClassId,1),"重新打开已投影道路");
            evidence.put("persisted_road_count",roads.getObjCount());
            if (roads.getObjCount()!=sourceIds.size()) throw new IllegalStateException("重新打开后道路数量不一致");
            evidence.put("projected_sref_id",roads.getsrID());
            SRefData actualSref=db.getSRef(roads.getsrID());
            if (actualSref==null) throw new IllegalStateException("投影后道路缺少空间参考");
            try { evidence.put("projected_wkt",actualSref.toWkt()); }
            finally { actualSref.dispose(); }
            evidence.put("range_recalculation_return",roads.calRange());
            Rect extent=roads.getRange();
            if (extent==null || !extent.isValid()) throw new IllegalStateException("投影后道路范围无效");
            evidence.put("projected_bounds",Arrays.asList(extent.getXMin(),extent.getYMin(),extent.getXMax(),extent.getYMax()));
            evidence.put("existing_network_id",roads.getgNetID());
            if (roads.getgNetID()>0) throw new IllegalStateException("新道路类已属于其他网络，停止建网");
            evidence.put("stage","create_network_dataset");
            // Official GDBCatalogPane exposes network creation under an XFds, not the DB root.
            // Create it with the persisted projected SRef, then move only our new exercise class.
            int datasetId=Math.toIntExact(db.createFds("exercise_transport",roads.getsrID()));
            evidence.put("dataset_create_return",datasetId);
            require(datasetId,"创建路网要素数据集");
            require(roads.setdsID(datasetId),"将道路归入路网要素数据集");
            roads.close();
            require(roads.open(roadClassId,1),"核验数据集中的道路");
            evidence.put("road_dataset_id",roads.getdsID());
            evidence.put("roads_url",roads.getURL());
            int[] members=db.getXclses(XClsType.XSFCls,datasetId);
            evidence.put("dataset_road_class_ids",members);
            com.mapgis.floodguard.business.NetworkBuildPreflight.check(
                    datasetId,roads.getdsID(),roadClassId,members,sourceIds.size(),roads.getObjCount());
            // Official CreateNetclsDialog builds from class IDs, without holding an open input class.
            // Release our writer/read handle before the native builder modifies the input topology.
            roads.close();
            evidence.put("input_class_closed",!roads.hasOpened());
            if (roads.hasOpened()) throw new IllegalStateException("建网前无法关闭道路线类");
            evidence.put("stage","build_network");
            evidence.put("network_parameters",Map.of("name","exercise_network","tolerance",0.1,"change_geometry",true,"dataset_id",datasetId));
            features=new NetFeatureList(); weights=new NetWeightList(); fields=new NetWeightFldList();
            NetFeature membership=new NetFeature(); membership.setFClsID(roadClassId); membership.setAsComplex(false);
            evidence.put("feature_list_append_return",features.append(membership));
            // Match official CreateNetclsDialog: weights and field bindings are supplied to create(),
            // not appended after edges already exist (which left some native values null in this SDK).
            NetWeight lengthWeight=new NetWeight();
            lengthWeight.setWgtName(MapGisExerciseWeights.LENGTH_WEIGHT);
            // mpLength already stores the complete impedance in metres. A ratio weight
            // makes MapGIS expose the default multiplier (1.0), not the field value.
            lengthWeight.setWgtType(WgtType.absoluteType);
            lengthWeight.setDataType(com.zondy.mapgis.att.Field.FieldType.fldDouble);
            lengthWeight.setBiteSize((short)0); lengthWeight.setWgtID(1);
            evidence.put("weight_list_append_return",weights.append(lengthWeight));
            NetWeightFld lengthBinding=new NetWeightFld();
            lengthBinding.setWgtFldID(1); lengthBinding.setFldName("mpLength");
            lengthBinding.setWgtID(1); lengthBinding.setFClsID(roadClassId);
            evidence.put("weight_field_list_append_return",fields.append(lengthBinding));
            net=new NetCls(db);
            int networkId=Math.toIntExact(net.create("exercise_network",0.1,true,datasetId,features,weights,fields));
            evidence.put("network_create_return",networkId);
            require(networkId,"MapGIS几何建网");
            evidence.put("stage","verify_persisted_network");
            evidence.put("network_close_return",net.close());
            // NetCls.close() deletes the native object and clears its handle in this SDK.
            // Unlike SFeatureCls, open() does not recreate that handle. Use a fresh wrapper.
            net=new NetCls(db);
            long reopenResult=net.open(networkId,1);
            evidence.put("network_reopen_return",reopenResult);
            require(reopenResult,"重新打开新建网络");
            int[] networks=db.getXclses(XClsType.XGNet,datasetId);
            evidence.put("dataset_network_ids",networks);
            if (networks==null || Arrays.stream(networks).noneMatch(id -> id==networkId))
                throw new IllegalStateException("新网络未登记在目标要素数据集中");
            if (net.getEdgeCount()<=0 || net.getNodCount()<=0) throw new IllegalStateException("Native network is empty");
            evidence.put("stage","verify_source_edge_mapping");
            Map<String,List<Integer>> mapping=new LinkedHashMap<>();
            for (var item:sourceIds.entrySet()) {
                var nativeIds=net.getSubEdgeS(roadClassId,Math.toIntExact(item.getValue()));
                if (nativeIds==null) throw new IllegalStateException("Missing native sub-edge mapping");
                try {
                    List<Integer> edges=new ArrayList<>();
                    for (int i=0;i<nativeIds.size();i++) edges.add(nativeIds.get(i));
                    if (edges.isEmpty() || edges.stream().anyMatch(e -> e<=0)) throw new IllegalStateException("Unmapped source road");
                    mapping.put(item.getKey(),edges);
                } finally { nativeIds.dispose(); }
            }
            evidence.put("network_url",net.getURL()); evidence.put("source_edge_ids",mapping);
            evidence.put("node_count",net.getNodCount()); evidence.put("edge_count",net.getEdgeCount());
            evidence.put("native_network_created",true);
            evidence.put("stage","topology_created");
            evidence.put("warning","Topology created; minute weights, resource-node binding and route acceptance still required. Exercise resources are not real assets.");
            boolean routingReady=false;
            try {
                MapGisExerciseWeights.prepare(net,roadClassId,mapping,source,output);
                evidence.put("minute_defaults_verified",true);
                routingReady=true;
            } catch (Exception | LinkageError preparationError) {
                // A later business preparation failure must not erase successful topology acceptance.
                evidence.put("minute_defaults_verified",false);
                evidence.put("dispatch_preparation_error",preparationError.toString());
            }
            evidence.put("dispatch_preparation_file",output.resolve("dispatch-preparation.json").toString());
            if (routingReady) {
                try {
                    com.mapgis.floodguard.business.NativeRoutingGate.require(true);
                    MapGisExerciseDispatch.verify(net,(String)evidence.get("roads_url"),sourceIds,mapping,source,output);
                    evidence.put("exercise_routes_verified",true);
                } catch (Exception | LinkageError dispatchError) {
                    evidence.put("exercise_routes_verified",false);
                    evidence.put("exercise_dispatch_error",dispatchError.toString());
                }
            } else {
                evidence.put("exercise_routes_verified",false);
                evidence.put("exercise_dispatch_skipped","Projected geometry or native topology did not pass verification; native routing was not called to protect the host process.");
            }
            return output.resolve("network-build.json");
        } catch (Exception | LinkageError error) {
            evidence.put("error",error.toString()); throw error;
        } finally {
            // Persist evidence even when a native initialization or partial build fails.
            try { Files.writeString(output.resolve("network-build.json"),json.writerWithDefaultPrettyPrinter().writeValueAsString(evidence),StandardOpenOption.CREATE_NEW); }
            finally {
                if (net!=null) net.close(); if (roads!=null) roads.close(); if (db!=null) db.close();
                if (features!=null) features.dispose(); if (weights!=null) weights.dispose(); if (fields!=null) fields.dispose();
                if (geographic!=null) geographic.dispose(); if (projected!=null) projected.dispose();
                if (createParam!=null) createParam.dispose(); if (dataFile!=null) dataFile.dispose(); if (extension!=null) extension.dispose();
                if (server!=null) server.disConnect();
            }
        }
    }
    private static void require(long code,String step) { if (code<=0) throw new IllegalStateException(step+"失败："+code); }
}
