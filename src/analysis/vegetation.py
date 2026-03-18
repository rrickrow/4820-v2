"""
植被动态响应分析模块
====================
分析河道变迁对周围植被的影响，核心方法：
  1. 以河道为中心建立缓冲区（0–1 km / 1–3 km / 3–5 km）
  2. 逐缓冲区统计 NDVI/FVC 均值及变化趋势
  3. 空间叠加分析：河道侵蚀区 vs 植被退化区空间耦合

用法示例
--------
>>> from src.analysis.vegetation import VegetationResponseAnalyzer
>>> analyzer = VegetationResponseAnalyzer(resolution_m=30)
>>> stats = analyzer.buffer_stats(water_mask, ndvi_da, buffer_distances_m=[1000, 3000, 5000])
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import xarray as xr


class VegetationResponseAnalyzer:
    """
    植被对河道变迁的响应分析器。

    Parameters
    ----------
    resolution_m : float  空间分辨率（米）
    """

    def __init__(self, resolution_m: float = 30.0) -> None:
        self.res = resolution_m

    def buffer_stats(
        self,
        water_mask: xr.DataArray,
        ndvi: xr.DataArray,
        buffer_distances_m: List[float] = None,
    ) -> pd.DataFrame:
        """
        在河道不同缓冲区内统计 NDVI 均值。

        Parameters
        ----------
        water_mask : xr.DataArray  bool 水体掩膜（单年）
        ndvi : xr.DataArray  NDVI（同年，与 water_mask 空间对齐）
        buffer_distances_m : list of float  缓冲区距离（米），默认 [1000, 3000, 5000]

        Returns
        -------
        pd.DataFrame
            列：buffer_km, pixel_count, ndvi_mean, ndvi_std
        """
        from scipy.ndimage import distance_transform_edt

        if buffer_distances_m is None:
            buffer_distances_m = [1000.0, 3000.0, 5000.0]

        # 到最近水体像元的距离（米）
        not_water = ~water_mask.values.astype(bool)
        dist_pixels = distance_transform_edt(not_water)
        dist_m = dist_pixels * self.res

        ndvi_vals = ndvi.values
        records = []
        prev_dist = 0.0

        for dist in sorted(buffer_distances_m):
            zone_mask = (dist_m > prev_dist) & (dist_m <= dist)
            zone_ndvi = ndvi_vals[zone_mask & ~np.isnan(ndvi_vals)]

            records.append(
                {
                    "buffer_km": f"{prev_dist/1000:.0f}–{dist/1000:.0f} km",
                    "pixel_count": int(zone_mask.sum()),
                    "ndvi_mean": round(float(zone_ndvi.mean()), 4) if zone_ndvi.size > 0 else np.nan,
                    "ndvi_std": round(float(zone_ndvi.std()), 4) if zone_ndvi.size > 0 else np.nan,
                }
            )
            prev_dist = dist

        return pd.DataFrame(records)

    def compute_spatial_coupling(
        self,
        water_change: xr.DataArray,
        ndvi_change: xr.DataArray,
    ) -> Dict[str, float]:
        """
        计算河道变化区域与植被变化区域的空间耦合系数。

        Parameters
        ----------
        water_change : xr.DataArray  河道面积变化（正=扩张，负=萎缩）
        ndvi_change : xr.DataArray  NDVI 变化（正=改善，负=退化）

        Returns
        -------
        dict  {'pearson_r': ..., 'overlap_ratio': ...}
        """
        from scipy.stats import pearsonr

        w = water_change.values.ravel()
        n = ndvi_change.values.ravel()

        # 去除 NaN
        valid = ~np.isnan(w) & ~np.isnan(n)
        if valid.sum() < 10:
            return {"pearson_r": np.nan, "p_value": np.nan, "overlap_ratio": np.nan}

        r, p = pearsonr(w[valid], n[valid])

        # 空间重叠率：河道扩张区 ∩ 植被退化区 / 河道扩张区
        expand_mask = w > 0
        degrade_mask = n < 0
        overlap = (expand_mask & degrade_mask & valid).sum()
        expand_total = (expand_mask & valid).sum()
        overlap_ratio = overlap / expand_total if expand_total > 0 else np.nan

        return {
            "pearson_r": round(float(r), 4),
            "p_value": round(float(p), 6),
            "overlap_ratio": round(float(overlap_ratio), 4),
        }

    def annual_ndvi_by_zone(
        self,
        water_masks: Dict[int, xr.DataArray],
        ndvi_timeseries: xr.DataArray,
        buffer_m: float = 2000.0,
    ) -> pd.DataFrame:
        """
        构建逐年河岸带 NDVI 均值时序表。

        Parameters
        ----------
        water_masks : dict  {year: water_mask}
        ndvi_timeseries : xr.DataArray  含 year 维度的 NDVI
        buffer_m : float  河岸带宽度（米）

        Returns
        -------
        pd.DataFrame  index=year, columns=['ndvi_mean', 'ndvi_std']
        """
        from scipy.ndimage import distance_transform_edt

        records = []
        for year in sorted(water_masks.keys()):
            if year not in ndvi_timeseries["year"].values:
                continue

            mask = water_masks[year].values.astype(bool)
            dist_m = distance_transform_edt(~mask) * self.res
            zone = (dist_m > 0) & (dist_m <= buffer_m)

            ndvi_vals = ndvi_timeseries.sel(year=year).values
            zone_ndvi = ndvi_vals[zone & ~np.isnan(ndvi_vals)]

            records.append(
                {
                    "year": year,
                    "ndvi_mean": round(float(zone_ndvi.mean()), 4) if zone_ndvi.size > 0 else np.nan,
                    "ndvi_std": round(float(zone_ndvi.std()), 4) if zone_ndvi.size > 0 else np.nan,
                }
            )

        return pd.DataFrame(records).set_index("year")
