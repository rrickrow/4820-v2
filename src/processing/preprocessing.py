"""
影像预处理模块
==============
功能：
  1. 辐射归一化（跨传感器归一化至 Landsat 8 基准）
  2. 时间合成（年度中值合成去除残余云噪声）
  3. 缺失数据插值
  4. 流域边界裁剪

用法示例
--------
>>> from src.processing.preprocessing import compute_annual_composite, clip_to_bbox
>>> annual = compute_annual_composite(ds_stack)
>>> clipped = clip_to_bbox(annual, bbox=[119.0, 40.0, 132.0, 50.0])
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import xarray as xr


def compute_annual_composite(
    ds: xr.Dataset,
    method: str = "median",
) -> xr.Dataset:
    """
    对年内多景影像进行时间合成（去除残余云噪声）。

    Parameters
    ----------
    ds : xr.Dataset
        包含时间维度的多波段 Dataset（已做云掩膜）。
    method : str
        合成方法：
        - "median"  中值合成（默认，最稳健）
        - "mean"    均值合成
        - "max_ndvi" 最大 NDVI 合成（保留植被状态最好景）

    Returns
    -------
    xr.Dataset  时间维度已折叠的年度合成影像
    """
    if method == "median":
        return ds.median(dim="time", skipna=True, keep_attrs=True)
    elif method == "mean":
        return ds.mean(dim="time", skipna=True, keep_attrs=True)
    elif method == "max_ndvi":
        if "nir" not in ds and "red" not in ds:
            raise ValueError("max_ndvi 合成需要 nir 和 red 波段。")
        ndvi = (ds["nir"] - ds["red"]) / (ds["nir"] + ds["red"] + 1e-10)
        best_idx = ndvi.argmax(dim="time")
        return ds.isel(time=best_idx)
    else:
        raise ValueError(f"不支持的合成方法: {method}。可选: median, mean, max_ndvi")


def normalize_reflectance(
    ds: xr.Dataset,
    reference_ds: Optional[xr.Dataset] = None,
    method: str = "histogram_match",
) -> xr.Dataset:
    """
    跨传感器辐射归一化（使不同传感器的反射率值可比较）。

    Parameters
    ----------
    ds : xr.Dataset
        待归一化的影像（如 Landsat 5/7）。
    reference_ds : xr.Dataset, optional
        参考影像（如 Landsat 8）。若为 None，则仅做线性归一化到 [0,1]。
    method : str
        归一化方法：
        - "histogram_match"  直方图匹配（近似替代 6S 模型，简单高效）
        - "min_max"          线性拉伸至 [0, 1]

    Returns
    -------
    xr.Dataset  归一化后的影像
    """
    if method == "min_max":
        normalized = {}
        for var in ds.data_vars:
            band = ds[var]
            vmin = float(band.min(skipna=True))
            vmax = float(band.max(skipna=True))
            if vmax > vmin:
                normalized[var] = (band - vmin) / (vmax - vmin)
            else:
                normalized[var] = band
        return xr.Dataset(normalized, attrs=ds.attrs)

    elif method == "histogram_match":
        if reference_ds is None:
            raise ValueError("histogram_match 方法需要提供 reference_ds。")
        normalized = {}
        for var in ds.data_vars:
            if var in reference_ds.data_vars:
                normalized[var] = _histogram_match(ds[var], reference_ds[var])
            else:
                normalized[var] = ds[var]
        return xr.Dataset(normalized, attrs=ds.attrs)

    else:
        raise ValueError(f"不支持的归一化方法: {method}")


def _histogram_match(
    source: xr.DataArray,
    reference: xr.DataArray,
    n_bins: int = 256,
) -> xr.DataArray:
    """
    对 source 影像进行直方图匹配，使其分布接近 reference。

    基于累积分布函数（CDF）映射实现。
    """
    src_vals = source.values.ravel()
    ref_vals = reference.values.ravel()

    # 去除 NaN
    src_valid = src_vals[~np.isnan(src_vals)]
    ref_valid = ref_vals[~np.isnan(ref_vals)]

    if src_valid.size == 0 or ref_valid.size == 0:
        return source

    # 计算 CDF
    src_hist, src_edges = np.histogram(src_valid, bins=n_bins, density=True)
    ref_hist, ref_edges = np.histogram(ref_valid, bins=n_bins, density=True)

    src_cdf = np.cumsum(src_hist) * (src_edges[1] - src_edges[0])
    ref_cdf = np.cumsum(ref_hist) * (ref_edges[1] - ref_edges[0])
    src_cdf = np.clip(src_cdf, 0, 1)
    ref_cdf = np.clip(ref_cdf, 0, 1)

    # 建立映射关系
    src_centers = (src_edges[:-1] + src_edges[1:]) / 2
    ref_centers = (ref_edges[:-1] + ref_edges[1:]) / 2
    mapped = np.interp(src_cdf, ref_cdf, ref_centers)

    # 应用映射
    result = np.interp(source.values, src_centers, mapped)
    result = np.where(np.isnan(source.values), np.nan, result)

    return xr.DataArray(result, coords=source.coords, dims=source.dims, attrs=source.attrs)


def fill_missing_by_interpolation(
    ds_list: List[xr.Dataset],
    years: List[int],
) -> List[xr.Dataset]:
    """
    对缺失年份使用前后年份线性插值填充。

    Parameters
    ----------
    ds_list : list of xr.Dataset
        年度合成影像列表（顺序与 years 对应，缺失年份用 None 占位）。
    years : list of int

    Returns
    -------
    list of xr.Dataset  填充后的完整列表
    """
    result = list(ds_list)
    n = len(result)

    for i, ds in enumerate(result):
        if ds is not None:
            continue

        # 找最近的非空前驱和后继
        prev_idx = next((j for j in range(i - 1, -1, -1) if result[j] is not None), None)
        next_idx = next((j for j in range(i + 1, n) if result[j] is not None), None)

        if prev_idx is not None and next_idx is not None:
            t_prev, t_next = years[prev_idx], years[next_idx]
            t_curr = years[i]
            weight = (t_curr - t_prev) / (t_next - t_prev)
            interpolated = {}
            for var in result[prev_idx].data_vars:
                interpolated[var] = (
                    result[prev_idx][var] * (1 - weight)
                    + result[next_idx][var] * weight
                )
            result[i] = xr.Dataset(interpolated)
        elif prev_idx is not None:
            result[i] = result[prev_idx]
        elif next_idx is not None:
            result[i] = result[next_idx]

    return result


def clip_to_bbox(
    ds: xr.Dataset,
    bbox: Tuple[float, float, float, float],
) -> xr.Dataset:
    """
    按经纬度范围裁剪 xarray Dataset（使用 rioxarray）。

    Parameters
    ----------
    ds : xr.Dataset
    bbox : tuple  (west, south, east, north)

    Returns
    -------
    xr.Dataset
    """
    import rioxarray  # noqa: F401  触发 rioxarray accessor 注册

    from shapely.geometry import box

    west, south, east, north = bbox
    geom = box(west, south, east, north)
    clipped = ds.rio.clip([geom.__geo_interface__], crs="EPSG:4326", drop=True)
    return clipped
