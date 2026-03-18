"""
NDVI 与植被覆盖度（FVC）计算模块
==================================
功能：
  1. 计算 NDVI 归一化植被指数
  2. 计算 FVC 植被覆盖度（像元二分模型）
  3. 年际趋势分析（Sen 斜率 + Mann-Kendall 检验）
  4. 植被退化 / 恢复区域识别

用法示例
--------
>>> from src.analysis.ndvi_fvc import compute_ndvi, compute_fvc, compute_trend
>>> ndvi = compute_ndvi(ds)
>>> fvc = compute_fvc(ndvi)
>>> slope, p_value = compute_trend(ndvi_timeseries)
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import xarray as xr


def compute_ndvi(ds: xr.Dataset) -> xr.DataArray:
    """
    计算 NDVI 归一化植被指数。

    NDVI = (NIR - Red) / (NIR + Red)

    Parameters
    ----------
    ds : xr.Dataset  需含 nir 和 red 波段

    Returns
    -------
    xr.DataArray  NDVI [-1, 1]
    """
    nir = ds["nir"].astype(float)
    red = ds["red"].astype(float)
    ndvi = (nir - red) / (nir + red + 1e-10)
    ndvi = ndvi.clip(-1.0, 1.0)
    ndvi.attrs = {"long_name": "归一化植被指数 (NDVI)", "units": "dimensionless"}
    return ndvi


def compute_fvc(
    ndvi: xr.DataArray,
    ndvi_soil: float = 0.05,
    ndvi_veg: float = 0.85,
) -> xr.DataArray:
    """
    基于像元二分模型计算植被覆盖度（FVC）。

    FVC = (NDVI - NDVI_soil) / (NDVI_veg - NDVI_soil)

    Parameters
    ----------
    ndvi : xr.DataArray
    ndvi_soil : float  裸地 NDVI（NDVImin），默认 0.05
    ndvi_veg : float  全覆盖 NDVI（NDVImax），默认 0.85

    Returns
    -------
    xr.DataArray  FVC [0, 1]
    """
    fvc = (ndvi - ndvi_soil) / (ndvi_veg - ndvi_soil + 1e-10)
    fvc = fvc.clip(0.0, 1.0)
    fvc.attrs = {"long_name": "植被覆盖度 (FVC)", "units": "fraction [0,1]"}
    return fvc


def compute_trend(
    timeseries: xr.DataArray,
    year_dim: str = "year",
) -> Tuple[xr.DataArray, xr.DataArray]:
    """
    逐像元计算时序趋势（Theil-Sen 斜率 + Mann-Kendall 显著性检验）。

    Parameters
    ----------
    timeseries : xr.DataArray
        含 year 维度的植被指数时间序列（如 NDVI 或 FVC）。
    year_dim : str  时间维度名称

    Returns
    -------
    (slope, p_value) : tuple of xr.DataArray
        slope  : Theil-Sen 斜率（每年变化量）
        p_value: Mann-Kendall 检验 p 值（< 0.05 表示趋势显著）
    """
    try:
        import pymannkendall as mk
    except ImportError as exc:
        raise ImportError(
            "pymannkendall 包未安装。请运行: pip install pymannkendall"
        ) from exc

    data = timeseries.values  # shape: (n_years, y, x)
    n_years, ny, nx = data.shape

    slope_arr = np.full((ny, nx), np.nan, dtype=float)
    pval_arr = np.full((ny, nx), np.nan, dtype=float)

    for i in range(ny):
        for j in range(nx):
            ts = data[:, i, j]
            valid = ~np.isnan(ts)
            if valid.sum() < 5:
                continue
            result = mk.original_test(ts[valid])
            slope_arr[i, j] = result.slope
            pval_arr[i, j] = result.p

    # 提取空间坐标（去掉年份维度）
    spatial_coords = {k: v for k, v in timeseries.coords.items() if k != year_dim}
    spatial_dims = [d for d in timeseries.dims if d != year_dim]

    slope_da = xr.DataArray(
        slope_arr,
        dims=spatial_dims,
        coords=spatial_coords,
        attrs={"long_name": "Theil-Sen 斜率", "units": f"{timeseries.attrs.get('units', '')}/year"},
    )
    pval_da = xr.DataArray(
        pval_arr,
        dims=spatial_dims,
        coords=spatial_coords,
        attrs={"long_name": "Mann-Kendall p 值", "units": "dimensionless"},
    )

    return slope_da, pval_da


def classify_vegetation_change(
    slope: xr.DataArray,
    p_value: xr.DataArray,
    significance: float = 0.05,
) -> xr.DataArray:
    """
    基于趋势斜率和显著性将植被变化分为 5 类。

    分类：
      0 - 无显著变化
      1 - 显著改善（slope > 0, p < significance）
      2 - 轻微改善（slope > 0, p >= significance）
      3 - 显著退化（slope < 0, p < significance）
      4 - 轻微退化（slope < 0, p >= significance）

    Returns
    -------
    xr.DataArray  整型分类图（0–4）
    """
    s = slope.values
    p = p_value.values

    result = np.zeros_like(s, dtype=np.int8)
    result[(s > 0) & (p < significance)] = 1
    result[(s > 0) & (p >= significance)] = 2
    result[(s < 0) & (p < significance)] = 3
    result[(s < 0) & (p >= significance)] = 4
    result[np.isnan(s)] = -1

    return xr.DataArray(
        result,
        coords=slope.coords,
        dims=slope.dims,
        attrs={
            "long_name": "植被变化分类",
            "categories": "0=无变化,1=显著改善,2=轻微改善,3=显著退化,4=轻微退化,-1=无数据",
        },
    )
