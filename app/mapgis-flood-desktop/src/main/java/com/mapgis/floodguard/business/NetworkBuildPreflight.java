package com.mapgis.floodguard.business;

import java.util.Arrays;

/** Preconditions for the official feature-dataset network workflow; no GIS computation. */
public final class NetworkBuildPreflight {
    private NetworkBuildPreflight() {}
    public static void check(int datasetId, int roadDatasetId, int roadClassId,
                             int[] members, long expectedCount, long persistedCount) {
        if (datasetId<=0 || roadDatasetId!=datasetId)
            throw new IllegalStateException("道路与网络必须属于同一有效要素数据集，不能使用根目录ID 0");
        if (roadClassId<=0 || members==null || Arrays.stream(members).noneMatch(id -> id==roadClassId))
            throw new IllegalStateException("目标要素数据集中未查询到道路线类");
        if (expectedCount<=0 || persistedCount!=expectedCount)
            throw new IllegalStateException("归入数据集后道路数量不一致或为空");
    }
}
