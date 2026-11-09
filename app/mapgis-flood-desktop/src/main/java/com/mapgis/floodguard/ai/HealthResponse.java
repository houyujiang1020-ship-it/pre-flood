package com.mapgis.floodguard.ai;

public record HealthResponse(
        String status,
        boolean model_loaded,
        String device,
        String backend,
        boolean production_checkpoint_loaded) {
    public String displaySummary() {
        String kind = "siamunet-smoke".equals(backend) ? "SiamUnet 已训练烟测模型（精度未达标）"
                : "spectral-change-fallback".equals(backend) ? "fallback 图像变化分析（非训练模型）"
                : "未验证后端：" + backend;
        return "服务报告：" + kind + "；设备：" + device + "；"
                + (model_loaded ? "已加载" : "未加载")
                + "。像素数量不等于建筑栋数、道路条数或受淹面积；不可用于实际应急决策。";
    }
}
