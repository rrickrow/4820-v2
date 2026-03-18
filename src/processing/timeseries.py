"""
长时序数据集构建模块（已更新为 MODIS 主力数据源）
=======================================================
构建 2000–2024 年松辽流域年度遥感数据集。

数据源优先级（替代原 Landsat/GEE 方案）：
  1. MODIS MOD13Q1 NDVI 250 m（16 天合成，via Planetary Computer STAC）← 主力
  2. MODIS MOD09A1 地表反射率 500 m（8 天合成）← 水体/NDWI
  3. MODIS MOD44W 年度水体掩膜 250 m          ← 河道提取
  4. Sentinel-2 L2A（可选高分辨率补充）        ← 精细分析备用

以上均通过 Planetary Computer STAC 免费直连，无需 Google 账号，无需预下载。

用法示例
--------
>>> from src.processing.timeseries import TimeSeriesBuilder
>>> builder = TimeSeriesBuilder(bbox=[119.0, 40.0, 132.0, 50.0])
>>> ts = builder.build(start_year=2000, end_year=2023)
>>> ts["ndvi"].sel(year=2020).plot()
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import xarray as xr
from tqdm import tqdm

from config import (
    STUDY_AREA_BBOX,
    START_YEAR,
    END_YEAR,
    GROWING_SEASON_MONTHS,
    MAX_CLOUD_COVER,
    TARGET_CRS,
    NDVI_BARE_SOIL,
    NDVI_FULL_COVER,
)
from src.data.modis import MODISLoader
from src.processing.preprocessing import compute_annual_composite, fill_missing_by_interpolation


class TimeSeriesBuilder:
    """
    构建长时序（逐年）遥感数据集，主力数据源为 MODIS。

    Parameters
    ----------
    bbox : list of float
        研究区范围 [west, south, east, north]。
    months : list of int
        生长季月份，默认 config.GROWING_SEASON_MONTHS。
    ndvi_resolution : int
        NDVI 分辨率（米），默认 250 m（MOD13Q1）。
    sr_resolution : int
        地表反射率分辨率（米），默认 500 m（MOD09A1）。
    crs : str
    """

    def __init__(
        self,
        bbox: Optional[List[float]] = None,
        months: Optional[List[int]] = None,
        ndvi_resolution: int = 250,
        sr_resolution: int = 500,
        crs: str = TARGET_CRS,
    ) -> None:
        self.bbox = bbox or STUDY_AREA_BBOX
        self.months = months or GROWING_SEASON_MONTHS
        self.ndvi_resolution = ndvi_resolution
        self.sr_resolution = sr_resolution
        self.crs = crs
        self._modis = MODISLoader()

    def build(
        self,
        start_year: int = START_YEAR,
        end_year: int = END_YEAR,
        composite_method: str = "median",
        fill_missing: bool = True,
    ) -> xr.Dataset:
        """
        构建逐年时序数据集（MODIS 主力）。

        Parameters
        ----------
        start_year : int
        end_year : int
        composite_method : str  年度合成方法（"median" / "mean" / "max_ndvi"）
        fill_missing : bool     是否插值填充缺失年份

        Returns
        -------
        xr.Dataset
            坐标：year、y、x
            变量：ndvi, evi, ndwi, fvc, water_mask（可选）
        """
        years = list(range(start_year, end_year + 1))
        annual_composites: List[Optional[xr.Dataset]] = []

        for year in tqdm(years, desc="构建 MODIS 年度合成"):
            try:
                ds = self._build_single_year(year, composite_method)
                annual_composites.append(ds)
            except ValueError as e:
                print(f"警告：{year} 年数据不足，将在后处理中插值填充。原因：{e}")
                annual_composites.append(None)

        if fill_missing:
            annual_composites = fill_missing_by_interpolation(annual_composites, years)

        valid_pairs = [
            (y, ds) for y, ds in zip(years, annual_composites) if ds is not None
        ]
        if not valid_pairs:
            raise RuntimeError("所有年份均无有效数据，请检查数据访问配置。")

        valid_years = [p[0] for p in valid_pairs]
        combined = xr.concat([p[1] for p in valid_pairs], dim="year")
        combined["year"] = valid_years

        return combined

    def _build_single_year(
        self,
        year: int,
        composite_method: str,
    ) -> xr.Dataset:
        """加载并合成单年 MODIS 数据，返回含 ndvi/evi/ndwi/fvc 的 Dataset。"""
        # ── 1. MOD13Q1 NDVI 250 m（主力植被指数）──
        ndvi_ds = self._modis.load_ndvi(
            year=year,
            bbox=self.bbox,
            months=self.months,
            resolution=self.ndvi_resolution,
            crs=self.crs,
        )
        ndvi_composite = compute_annual_composite(ndvi_ds, method=composite_method)

        # ── 2. MOD09A1 地表反射率 500 m（用于计算 NDWI）──
        try:
            sr_ds = self._modis.load_surface_reflectance(
                year=year,
                bbox=self.bbox,
                months=self.months,
                resolution=self.sr_resolution,
                crs=self.crs,
            )
            sr_composite = compute_annual_composite(sr_ds, method=composite_method)
            ndwi = self._compute_ndwi(sr_composite)
        except ValueError:
            # MOD09A1 不可用时用 NDVI 代替（NDWI = NaN）
            ndwi = xr.full_like(ndvi_composite["ndvi"], fill_value=np.nan)
            ndwi.attrs = {"long_name": "NDWI（本年缺失 MOD09A1，填充 NaN）"}

        # ── 3. 计算 FVC 植被覆盖度 ──
        fvc = self._compute_fvc(ndvi_composite["ndvi"])

        # ── 4. 汇总为单年 Dataset ──
        ds = xr.Dataset(
            {
                "ndvi": ndvi_composite["ndvi"],
                "evi":  ndvi_composite["evi"],
                "ndwi": ndwi,
                "fvc":  fvc,
            }
        )
        return ds

    # ──────────────────────────────────────────
    # 辅助计算
    # ──────────────────────────────────────────

    @staticmethod
    def _compute_ndwi(sr_ds: xr.Dataset) -> xr.DataArray:
        """NDWI = (Green - NIR) / (Green + NIR)"""
        green = sr_ds["green"].astype(float)
        nir   = sr_ds["nir"].astype(float)
        ndwi  = (green - nir) / (green + nir + 1e-10)
        ndwi  = ndwi.clip(-1.0, 1.0)
        ndwi.attrs = {"long_name": "NDWI (MOD09A1)", "units": "dimensionless"}
        return ndwi

    @staticmethod
    def _compute_fvc(ndvi: xr.DataArray) -> xr.DataArray:
        """FVC = (NDVI - NDVImin) / (NDVImax - NDVImin)，范围 [0,1]"""
        fvc = (ndvi - NDVI_BARE_SOIL) / (NDVI_FULL_COVER - NDVI_BARE_SOIL + 1e-10)
        fvc = fvc.clip(0.0, 1.0)
        fvc.attrs = {"long_name": "植被覆盖度 FVC (像元二分模型)", "units": "fraction [0,1]"}
        return fvc
