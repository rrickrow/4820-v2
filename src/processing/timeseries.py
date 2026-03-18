"""
长时序数据集构建模块
====================
构建 1995–2025 年松辽流域年度遥感数据集，自动协调 Landsat 5/7/8/9 传感器切换，
融合 Sentinel-2（2015 年后），生成可直接用于分析的 xarray Dataset。

用法示例
--------
>>> from src.processing.timeseries import TimeSeriesBuilder
>>> builder = TimeSeriesBuilder(bbox=[119.0, 40.0, 132.0, 50.0])
>>> ts = builder.build(start_year=2015, end_year=2025)
>>> ts["ndvi"].sel(year=2020).plot()
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import xarray as xr
from tqdm import tqdm

from config import (
    STUDY_AREA_BBOX,
    START_YEAR,
    END_YEAR,
    GROWING_SEASON_MONTHS,
    MAX_CLOUD_COVER,
    TARGET_RESOLUTION,
    TARGET_CRS,
)
from src.data.landsat import LandsatLoader
from src.data.sentinel2 import Sentinel2Loader
from src.processing.preprocessing import compute_annual_composite, fill_missing_by_interpolation
from src.processing.fusion import SensorFusion


class TimeSeriesBuilder:
    """
    构建长时序（逐年）遥感数据集。

    Parameters
    ----------
    bbox : list of float
        研究区范围 [west, south, east, north]。
    months : list of int
        生长季月份，默认使用 config.GROWING_SEASON_MONTHS。
    max_cloud_cover : int
    resolution : int  空间分辨率（米）
    crs : str
    use_sentinel2 : bool
        是否融合 Sentinel-2（2015 年后），默认 True。
    """

    # Sentinel-2 首次可用年份
    SENTINEL2_START_YEAR = 2015

    def __init__(
        self,
        bbox: Optional[List[float]] = None,
        months: Optional[List[int]] = None,
        max_cloud_cover: int = MAX_CLOUD_COVER,
        resolution: int = TARGET_RESOLUTION,
        crs: str = TARGET_CRS,
        use_sentinel2: bool = True,
    ) -> None:
        self.bbox = bbox or STUDY_AREA_BBOX
        self.months = months or GROWING_SEASON_MONTHS
        self.max_cloud_cover = max_cloud_cover
        self.resolution = resolution
        self.crs = crs
        self.use_sentinel2 = use_sentinel2

        self._landsat = LandsatLoader()
        self._sentinel2 = Sentinel2Loader() if use_sentinel2 else None
        self._fusion = SensorFusion()

    def build(
        self,
        start_year: int = START_YEAR,
        end_year: int = END_YEAR,
        composite_method: str = "median",
        fill_missing: bool = True,
    ) -> xr.Dataset:
        """
        构建逐年时序数据集。

        Parameters
        ----------
        start_year : int
        end_year : int
        composite_method : str  年度合成方法（"median" / "mean" / "max_ndvi"）
        fill_missing : bool  是否插值填充缺失年份

        Returns
        -------
        xr.Dataset
            坐标：year（int）、y、x
            变量：blue, green, red, nir, swir1, swir2, ndvi, ndwi, fvc
        """
        years = list(range(start_year, end_year + 1))
        annual_composites: List[Optional[xr.Dataset]] = []

        for year in tqdm(years, desc="构建年度合成影像"):
            try:
                ds = self._build_single_year(year, composite_method)
                annual_composites.append(ds)
            except ValueError as e:
                print(f"警告：{year} 年数据不足，将在后处理中插值填充。原因：{e}")
                annual_composites.append(None)

        if fill_missing:
            annual_composites = fill_missing_by_interpolation(annual_composites, years)

        # 沿年份维度合并
        valid_pairs = [
            (year, ds) for year, ds in zip(years, annual_composites) if ds is not None
        ]
        if not valid_pairs:
            raise RuntimeError("所有年份均无有效数据，请检查数据访问配置。")

        valid_years = [p[0] for p in valid_pairs]
        valid_ds = [p[1] for p in valid_pairs]

        combined = xr.concat(valid_ds, dim="year")
        combined["year"] = valid_years

        # 计算派生指数
        combined = self._compute_indices(combined)

        return combined

    def _build_single_year(
        self,
        year: int,
        composite_method: str,
    ) -> xr.Dataset:
        """加载并合成单年数据。"""
        # 加载 Landsat
        ls_stack = self._landsat.load_year(
            year=year,
            bbox=self.bbox,
            months=self.months,
            max_cloud_cover=self.max_cloud_cover,
            resolution=self.resolution,
            crs=self.crs,
        )
        ls_composite = compute_annual_composite(ls_stack, method=composite_method)

        # 融合 Sentinel-2（2015 年起）
        if self.use_sentinel2 and year >= self.SENTINEL2_START_YEAR and self._sentinel2:
            try:
                s2_stack = self._sentinel2.load_year(
                    year=year,
                    bbox=self.bbox,
                    months=self.months,
                    max_cloud_cover=self.max_cloud_cover,
                    resolution=self.resolution,
                    crs=self.crs,
                )
                s2_composite = compute_annual_composite(s2_stack, method=composite_method)
                return self._fusion.fuse(ls_composite, s2_composite)
            except ValueError:
                # Sentinel-2 数据不足时退回纯 Landsat
                return ls_composite

        return ls_composite

    def _compute_indices(self, ds: xr.Dataset) -> xr.Dataset:
        """
        计算 NDVI、NDWI 和 FVC 植被覆盖度。

        NDVI = (NIR - Red) / (NIR + Red)
        NDWI = (Green - NIR) / (Green + NIR)   [McFeeters, 1996]
        FVC  = (NDVI - NDVI_min) / (NDVI_max - NDVI_min)
        """
        from config import NDVI_BARE_SOIL, NDVI_FULL_COVER

        nir = ds["nir"]
        red = ds["red"]
        green = ds["green"]

        ndvi = (nir - red) / (nir + red + 1e-10)
        ndwi = (green - nir) / (green + nir + 1e-10)
        fvc = (ndvi - NDVI_BARE_SOIL) / (NDVI_FULL_COVER - NDVI_BARE_SOIL)
        fvc = fvc.clip(0.0, 1.0)

        ds = ds.assign(
            ndvi=ndvi.assign_attrs({"long_name": "归一化植被指数", "units": "dimensionless"}),
            ndwi=ndwi.assign_attrs({"long_name": "归一化水体指数", "units": "dimensionless"}),
            fvc=fvc.assign_attrs({"long_name": "植被覆盖度", "units": "fraction [0,1]"}),
        )
        return ds
