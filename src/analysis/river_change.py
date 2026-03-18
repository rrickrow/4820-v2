"""
河道变迁检测模块
================
功能：
  1. 逐年河道面积统计
  2. 中心线迁移量化（摆动幅度与方向）
  3. 主槽宽度变化
  4. 河道变迁强度指数（Channel Migration Index, CMI）

用法示例
--------
>>> from src.analysis.river_change import RiverChangeAnalyzer
>>> analyzer = RiverChangeAnalyzer(resolution_m=30)
>>> stats = analyzer.compute_annual_stats(water_masks_dict)
>>> cmi = analyzer.compute_migration_index(water_masks_dict)
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import xarray as xr


class RiverChangeAnalyzer:
    """
    河道变迁综合分析器。

    Parameters
    ----------
    resolution_m : float  空间分辨率（米），默认 30 m
    """

    def __init__(self, resolution_m: float = 30.0) -> None:
        self.res = resolution_m
        self.pixel_area_km2 = (resolution_m / 1000) ** 2

    def compute_annual_stats(
        self,
        water_masks: Dict[int, xr.DataArray],
    ) -> pd.DataFrame:
        """
        计算逐年河道统计指标。

        Parameters
        ----------
        water_masks : dict  {year: water_mask_DataArray}

        Returns
        -------
        pd.DataFrame
            列：year, area_km2, perimeter_km, mean_width_m, max_width_m
        """
        from src.analysis.ndwi import compute_channel_width

        records = []
        for year, mask in sorted(water_masks.items()):
            water_np = mask.values.astype(bool)
            area = water_np.sum() * self.pixel_area_km2

            # 周长：统计水体边缘像元数
            from scipy.ndimage import binary_erosion

            eroded = binary_erosion(water_np)
            perimeter_pixels = (water_np & ~eroded).sum()
            perimeter_km = perimeter_pixels * self.res / 1000

            # 河道宽度
            width_da = compute_channel_width(mask, self.res)
            width_valid = width_da.values[~np.isnan(width_da.values)]
            mean_width = float(width_valid.mean()) if width_valid.size > 0 else np.nan
            max_width = float(width_valid.max()) if width_valid.size > 0 else np.nan

            records.append(
                {
                    "year": year,
                    "area_km2": round(area, 4),
                    "perimeter_km": round(perimeter_km, 4),
                    "mean_width_m": round(mean_width, 2),
                    "max_width_m": round(max_width, 2),
                }
            )

        return pd.DataFrame(records).set_index("year")

    def compute_migration_index(
        self,
        water_masks: Dict[int, xr.DataArray],
        reference_year: int = None,
    ) -> pd.DataFrame:
        """
        计算相对参考年份的河道变迁强度指数（CMI）。

        CMI = |面积变化率|（相对参考年份）

        Parameters
        ----------
        water_masks : dict
        reference_year : int, optional  参考年份，默认使用最早年份

        Returns
        -------
        pd.DataFrame  列：year, area_change_km2, cmi
        """
        years = sorted(water_masks.keys())
        if reference_year is None:
            reference_year = years[0]

        ref_area = water_masks[reference_year].values.astype(bool).sum() * self.pixel_area_km2

        records = []
        for year in years:
            area = water_masks[year].values.astype(bool).sum() * self.pixel_area_km2
            change = area - ref_area
            cmi = abs(change) / ref_area if ref_area > 0 else np.nan
            records.append({"year": year, "area_change_km2": round(change, 4), "cmi": round(cmi, 6)})

        return pd.DataFrame(records).set_index("year")

    def compute_centerline_shift(
        self,
        centerline_a: xr.DataArray,
        centerline_b: xr.DataArray,
    ) -> float:
        """
        估算两期中心线之间的平均横向偏移距离（米）。

        算法：对 centerline_a 中每个像元，找到 centerline_b 中最近的像元，
        统计所有距离的均值。

        Parameters
        ----------
        centerline_a, centerline_b : xr.DataArray  bool 中心线掩膜

        Returns
        -------
        float  平均横向偏移（米）
        """
        from scipy.ndimage import distance_transform_edt

        pts_a = np.argwhere(centerline_a.values.astype(bool))
        if pts_a.size == 0:
            return np.nan

        # 距离变换：centerline_b 外部到最近中心线像元的距离
        dist_from_b = distance_transform_edt(~centerline_b.values.astype(bool))
        shifts = dist_from_b[pts_a[:, 0], pts_a[:, 1]]

        return float(shifts.mean()) * self.res
