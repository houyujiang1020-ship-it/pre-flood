package com.mapgis.floodguard.mapgis;

import com.mapgis.floodguard.business.ExposureAssessment;
import com.zondy.mapgis.geodatabase.*;
import com.zondy.mapgis.geometry.Geometry;
import com.zondy.mapgis.srs.SRefData;
import java.util.*;

/** Caller supplies already opened, same-CRS data. Does not open, reproject, or mutate user datasets. */
public final class MapGisExposureQuery {
    public List<ExposureAssessment.Hit> query(SFeatureCls features, String datasetId,
            ExposureAssessment.Kind kind, String verifiedDatasetWkt, String patchWkt, Map<String, Geometry> patches) {
        if (features == null || !features.hasOpened()) throw new IllegalArgumentException("实体数据集未打开");
        if (!sameCrs(verifiedDatasetWkt,patchWkt))
            throw new IllegalArgumentException("实体与斑块坐标系未核对一致，拒绝空间查询");
        List<ExposureAssessment.Hit> hits = new ArrayList<>();
        for (var patch : patches.entrySet()) {
            QueryDef filter = new QueryDef();
            RecordSet records = null;
            try {
                if (filter.setSpatial(patch.getValue(), SpaQueryMode.ModeIntersect) <= 0)
                    throw new IllegalStateException("MapGIS无法设置精确相交条件");
                records = features.query(filter);
                if (records == null) throw new IllegalStateException("空间查询失败，不能视为零命中");
                int count = records.getCount();
                if (count < 0) throw new IllegalStateException("无效查询记录数");
                if (count > 0) records.moveFirst();
                for (int i = 0; i < count; i++) {
                    if (records.isEOF()) throw new IllegalStateException("空间查询游标提前结束");
                    long id = records.getID();
                    if (id <= 0) throw new IllegalStateException("实体记录缺少有效ID");
                    hits.add(new ExposureAssessment.Hit(datasetId, Long.toString(id), kind, patch.getKey()));
                    if (i + 1 < count) records.moveNext();
                }
            } finally {
                if (records != null) records.dispose();
                filter.dispose();
            }
        }
        return List.copyOf(hits);
    }
    static boolean sameCrs(String firstWkt,String secondWkt) {
        if (firstWkt==null || firstWkt.isBlank() || secondWkt==null || secondWkt.isBlank()) return false;
        SRefData first=SRefData.fromWkt(firstWkt,false), second=SRefData.fromWkt(secondWkt,false);
        try { return first!=null && second!=null && first.isIdentical(second); }
        finally { if(first!=null) first.dispose(); if(second!=null) second.dispose(); }
    }
}
