"""
NDWI 水体提取与河道边界分析模块
=================================
功能：
  1. 基于 NDWI 阈值二值化提取水体掩膜
  2. 形态学后处理（去噪、填充小洞）
  3. 提取河道边界多边形
  4. 骨架化提取河道中心线

NDWI = (Green - NIR) / (Green + NIR)  [McFeeters, 1996]

用法示例
--------
>>> from src.analysis.ndwi import extract_water_body, extract_centerline
>>> water_mask = extract_water_body(ds)          # 二值水体掩膜
>>> centerline = extract_centerline(water_mask)  # 河道中心线
"""

from __future__ import annotations

import numpy as np
import xarray as xr


def compute_ndwi(ds: xr.Dataset) -> xr.DataArray:
    """
    计算 NDWI 归一化水体指数。

    Parameters
    ----------
    ds : xr.Dataset  需含 green 和 nir 波段

    Returns
    -------
    xr.DataArray  NDWI 值，范围 [-1, 1]
    """
    green = ds["green"].astype(float)
    nir = ds["nir"].astype(float)
    ndwi = (green - nir) / (green + nir + 1e-10)
    ndwi.attrs = {"long_name": "归一化水体指数 (NDWI)", "units": "dimensionless"}
    return ndwi


def extract_water_body(
    ds: xr.Dataset,
    threshold: float = 0.0,
    min_area_pixels: int = 100,
) -> xr.DataArray:
    """
    基于 NDWI 阈值提取水体二值掩膜，并去除面积小于阈值的噪声斑块。

    Parameters
    ----------
    ds : xr.Dataset
    threshold : float  NDWI 阈值，默认 0.0（NDWI > 0 判定为水体）
    min_area_pixels : int  最小水体面积（像元数），过滤噪声

    Returns
    -------
    xr.DataArray  bool 类型，True 表示水体
    """
    from skimage import morphology

    ndwi = compute_ndwi(ds)
    water = ndwi > threshold

    # 形态学后处理：去除小斑块、填充小孔洞
    water_np = water.values.astype(bool)

    # 处理 NaN
    valid_mask = ~np.isnan(ndwi.values)
    water_np = water_np & valid_mask

    # 去除小斑块
    water_np = morphology.remove_small_objects(water_np, min_size=min_area_pixels)
    # 填充小孔洞
    water_np = morphology.remove_small_holes(water_np, area_threshold=min_area_pixels // 2)

    result = xr.DataArray(
        water_np,
        coords=ndwi.coords,
        dims=ndwi.dims,
        attrs={"long_name": "水体掩膜", "threshold": threshold},
    )
    return result


def extract_centerline(
    water_mask: xr.DataArray,
) -> xr.DataArray:
    """
    使用形态学骨架化提取河道中心线。

    Parameters
    ----------
    water_mask : xr.DataArray  bool 水体掩膜

    Returns
    -------
    xr.DataArray  bool 类型，True 表示中心线像元
    """
    from skimage.morphology import skeletonize

    skeleton = skeletonize(water_mask.values.astype(bool))
    return xr.DataArray(
        skeleton,
        coords=water_mask.coords,
        dims=water_mask.dims,
        attrs={"long_name": "河道中心线（骨架化）"},
    )


def compute_water_area(
    water_mask: xr.DataArray,
    pixel_area_km2: float = 0.0009,
) -> float:
    """
    计算水体总面积（km²）。

    Parameters
    ----------
    water_mask : xr.DataArray  bool 水体掩膜
    pixel_area_km2 : float  每个像元面积（km²），30 m 分辨率默认 0.0009 km²

    Returns
    -------
    float  水体面积（km²）
    """
    count = int(water_mask.values.sum())
    return count * pixel_area_km2


def compute_channel_width(
    water_mask: xr.DataArray,
    resolution_m: float = 30.0,
) -> xr.DataArray:
    """
    逐像元估算河道宽度（基于局部距离变换）。

    Parameters
    ----------
    water_mask : xr.DataArray  bool 水体掩膜
    resolution_m : float  像元分辨率（米）

    Returns
    -------
    xr.DataArray  河道宽度（米）
    """
    from scipy.ndimage import distance_transform_edt

    dist = distance_transform_edt(water_mask.values.astype(bool))
    # 宽度 = 2 × 到岸线距离（最大宽度为中心线处距离的两倍）
    width = dist * 2 * resolution_m
    width = np.where(water_mask.values, width, np.nan)

    return xr.DataArray(
        width,
        coords=water_mask.coords,
        dims=water_mask.dims,
        attrs={"long_name": "河道宽度", "units": "m"},
    )
