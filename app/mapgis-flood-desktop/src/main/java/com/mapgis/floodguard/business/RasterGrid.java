package com.mapgis.floodguard.business;

/** Validates metadata supplied by MapGIS, without implementing GIS transformations. */
public record RasterGrid(int width, int height, String crs, double x, double y, double dx, double dy) {
    public record Point(double x, double y) {}
    public RasterGrid {
        if (width <= 0 || height <= 0 || crs == null || crs.isBlank()
                || !Double.isFinite(x) || !Double.isFinite(y) || !Double.isFinite(dx) || !Double.isFinite(dy)
                || dx <= 0 || dy >= 0) throw new IllegalArgumentException("需要有效空间参考及北向上栅格");
    }
    public void requireSame(RasterGrid other) {
        double tolerance = Math.min(Math.abs(dx), Math.abs(dy)) * 1e-6;
        if (other == null || width != other.width || height != other.height || !crs.equals(other.crs)
                || Math.abs(x - other.x) > tolerance || Math.abs(y - other.y) > tolerance
                || Math.abs(dx - other.dx) > tolerance || Math.abs(dy - other.dy) > tolerance)
            throw new IllegalArgumentException("两期影像坐标系、尺寸或像素网格不一致，请先在 MapGIS 配准");
    }
    /** Restores a model pixel centre through a recorded crop/resize to this original grid. */
    public Point modelPixelToMap(int column, int row, int modelWidth, int modelHeight,
                                 int cropX, int cropY, int cropWidth, int cropHeight) {
        if (modelWidth <= 0 || modelHeight <= 0 || column < 0 || row < 0
                || column >= modelWidth || row >= modelHeight || cropX < 0 || cropY < 0
                || cropWidth <= 0 || cropHeight <= 0 || (long)cropX + cropWidth > width
                || (long)cropY + cropHeight > height)
            throw new IllegalArgumentException("模型尺寸或裁剪范围超出原始影像");
        double originalX = cropX + (column + .5) * cropWidth / modelWidth;
        double originalY = cropY + (row + .5) * cropHeight / modelHeight;
        return new Point(x + originalX * dx, y + originalY * dy);
    }
}
