"""
多传感器影像融合模块
====================
将 Landsat（30 m）与 Sentinel-2（重采样至 30 m）的年度合成影像融合，
构建高时空一致性的长时序数据集（1995–2025）。

融合策略：
  - 2015 年前：仅 Landsat（5/7）
  - 2015–2021 年：Landsat 8 + Sentinel-2 加权平均（权重基于有效像元数）
  - 2022 年后：Landsat 8/9 + Sentinel-2 加权平均

用法示例
--------
>>> from src.processing.fusion import SensorFusion
>>> fusion = SensorFusion()
>>> fused = fusion.fuse(landsat_ds, sentinel2_ds)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import xarray as xr


class SensorFusion:
    """
    Landsat 与 Sentinel-2 影像加权融合。

    Parameters
    ----------
    weight_landsat : float
        融合时 Landsat 的权重，默认 0.5（等权重）。
    weight_sentinel2 : float
        融合时 Sentinel-2 的权重，默认 0.5。
    """

    def __init__(
        self,
        weight_landsat: float = 0.5,
        weight_sentinel2: float = 0.5,
    ) -> None:
        if abs(weight_landsat + weight_sentinel2 - 1.0) > 1e-6:
            raise ValueError("weight_landsat + weight_sentinel2 必须等于 1.0")
        self.w_ls = weight_landsat
        self.w_s2 = weight_sentinel2

    def fuse(
        self,
        landsat_ds: xr.Dataset,
        sentinel2_ds: Optional[xr.Dataset] = None,
    ) -> xr.Dataset:
        """
        融合 Landsat 与 Sentinel-2 年度合成影像。

        当 sentinel2_ds 为 None 时（2015 年前），直接返回 Landsat 影像。

        Parameters
        ----------
        landsat_ds : xr.Dataset  Landsat 年度合成
        sentinel2_ds : xr.Dataset, optional  Sentinel-2 年度合成（已重采样至 30 m）

        Returns
        -------
        xr.Dataset  融合后的影像
        """
        if sentinel2_ds is None:
            return landsat_ds

        common_vars = set(landsat_ds.data_vars) & set(sentinel2_ds.data_vars)
        fused = {}
        for var in common_vars:
            ls_band = landsat_ds[var]
            s2_band = sentinel2_ds[var]

            # 对齐空间坐标（必要时重采样 Sentinel-2 至 Landsat 格网）
            s2_aligned = s2_band.interp_like(ls_band, method="linear")

            # 基于有效像元数计算自适应权重
            ls_valid = (~np.isnan(ls_band)).astype(float)
            s2_valid = (~np.isnan(s2_aligned)).astype(float)
            total_valid = ls_valid * self.w_ls + s2_valid * self.w_s2
            total_valid = total_valid.where(total_valid > 0, np.nan)

            numerator = (
                xr.where(~np.isnan(ls_band), ls_band * self.w_ls, 0.0)
                + xr.where(~np.isnan(s2_aligned), s2_aligned * self.w_s2, 0.0)
            )
            fused[var] = numerator / total_valid

        return xr.Dataset(fused, attrs=landsat_ds.attrs)
