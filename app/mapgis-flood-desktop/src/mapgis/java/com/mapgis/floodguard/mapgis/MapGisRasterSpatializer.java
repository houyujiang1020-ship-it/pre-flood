package com.mapgis.floodguard.mapgis;

import com.zondy.mapgis.geodatabase.raster.RasterAccess;
import com.zondy.mapgis.geodatabase.raster.RasterDataset;
import com.zondy.mapgis.geodatabase.raster.RasterFormat;
import com.zondy.mapgis.geodatabase.raster.PaletteInterp;
import com.zondy.mapgis.geometry.Dot;
import java.nio.file.Files;
import java.nio.file.Path;
import java.io.IOException;

/** Native MapGIS raster conversion. Requires licensed host; compile verification is not runtime verification. */
public final class MapGisRasterSpatializer {
    public com.mapgis.floodguard.business.RasterGrid inspect(Path path) {
        RasterDataset dataset = new RasterDataset();
        try {
            require(dataset.open(path.toAbsolutePath().toString(), RasterAccess.Read), "检查输出栅格");
            return grid(dataset);
        } finally {
            if (dataset.hasOpened()) dataset.close(); dataset.dispose();
        }
    }
    public void validatePair(Path first, Path second) {
        RasterDataset before = new RasterDataset(), after = new RasterDataset();
        try {
            require(before.open(first.toAbsolutePath().toString(), RasterAccess.Read), "打开灾前参考");
            require(after.open(second.toAbsolutePath().toString(), RasterAccess.Read), "打开灾后参考");
            grid(before).requireSame(grid(after));
        } finally {
            if (before.hasOpened()) before.close(); before.dispose();
            if (after.hasOpened()) after.close(); after.dispose();
        }
    }
    private static com.mapgis.floodguard.business.RasterGrid grid(RasterDataset raster) {
        Dot origin = raster.pixelToMap(new Dot(0, 0));
        Dot east = raster.pixelToMap(new Dot(1, 0));
        Dot south = raster.pixelToMap(new Dot(0, 1));
        if (origin == null || east == null || south == null || raster.getSref() == null
                || Math.abs(east.getY() - origin.getY()) > 1e-10 || Math.abs(south.getX() - origin.getX()) > 1e-10)
            throw new IllegalArgumentException("影像必须有地理参考且无网格旋转");
        return new com.mapgis.floodguard.business.RasterGrid(raster.getWidth(), raster.getHeight(), raster.getSref().toWkt(),
                origin.getX(), origin.getY(), east.getX() - origin.getX(), south.getY() - origin.getY());
    }
    public Path spatialize(Path mask, Path reference, Path destination) throws IOException {
        if (!Files.isRegularFile(mask) || !Files.isRegularFile(reference)) throw new IllegalArgumentException("Mask/reference missing");
        if (Files.exists(destination)) throw new IllegalArgumentException("Refusing to overwrite existing raster: " + destination);
        Files.createDirectories(destination.toAbsolutePath().getParent());
        RasterDataset source = new RasterDataset(), pixels = new RasterDataset(), result = new RasterDataset();
        try {
            require(source.open(reference.toAbsolutePath().toString(), RasterAccess.Read), "打开参考影像");
            require(pixels.open(mask.toAbsolutePath().toString(), RasterAccess.Read), "打开分类掩膜");
            if (source.getWidth() != pixels.getWidth() || source.getHeight() != pixels.getHeight())
                throw new IllegalArgumentException("掩膜必须与参考影像同尺寸、同像素网格");
            if (source.getSref() == null || source.getRange() == null || !source.getRange().isValid())
                throw new IllegalArgumentException("参考影像缺少有效空间参考/范围");
            Dot origin = source.pixelToMap(new Dot(0, 0));
            Dot east = source.pixelToMap(new Dot(1, 0));
            Dot south = source.pixelToMap(new Dot(0, 1));
            if (origin == null || east == null || south == null
                    || east.getX() <= origin.getX() || south.getY() >= origin.getY()
                    || Math.abs(east.getY() - origin.getY()) > 1e-10
                    || Math.abs(south.getX() - origin.getX()) > 1e-10)
                throw new IllegalArgumentException("当前空间化仅支持北向上无旋转网格，请先使用 MapGIS 校正");
            require(pixels.convertTo(RasterFormat.GTiff, destination.toAbsolutePath().toString(), null), "转换 GeoTIFF");
            require(result.open(destination.toAbsolutePath().toString(), RasterAccess.Write), "打开输出栅格");
            require(result.setRange(source.getRange()), "写入地理范围");
            require(result.setSref(source.getSref()), "写入空间参考");
            if (result.getBandNum() == 1) {
                var interpretation = result.getColorInterp();
                interpretation.setInterp(PaletteInterp.Gray);
                require(result.setColorInterp(interpretation), "设置单波段灰度显示（避免无颜色表的调色板模式）");
            }
            require(result.close(), "保存输出栅格");
            require(result.open(destination.toAbsolutePath().toString(), RasterAccess.Read), "重新打开验证");
            if (result.getSref() == null || result.getWidth() != source.getWidth() || result.getHeight() != source.getHeight())
                throw new IllegalStateException("MapGIS 输出空间化验证失败");
            grid(source).requireSame(grid(result));
            return destination;
        } finally {
            if (result.hasOpened()) result.close(); result.dispose();
            if (pixels.hasOpened()) pixels.close(); pixels.dispose();
            if (source.hasOpened()) source.close(); source.dispose();
        }
    }

    private static void require(long code, String operation) {
        if (code <= 0) throw new IllegalStateException("MapGIS " + operation + "失败，返回码 " + code);
    }
}
