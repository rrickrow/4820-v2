"""
MODIS 数据获取模块（主力数据源）
==================================
通过 **Microsoft Planetary Computer STAC API** 免费直连获取 MODIS 产品，
无需 Google 账号、无需预下载，支持懒加载流式读取。

支持产品：
  - MOD13Q1  NDVI/EVI 16 天合成，250 m（Collection ID: modis-13Q1-061）
  - MOD09A1  地表反射率 8 天合成，500 m（Collection ID: modis-09A1-061）
  - MOD44W   年度水体掩膜，250 m  （Collection ID: modis-44W-061）

相比 Landsat 30 m，MODIS 500 m 数据量约小 278 倍，非常适合
松辽流域（~1200 × 1000 km）的长时序分析。

用法示例
--------
>>> from src.data.modis import MODISLoader
>>> loader = MODISLoader()

>>> # 获取 2020 年生长季 NDVI（250 m，MOD13Q1）
>>> ndvi_ds = loader.load_ndvi(year=2020, bbox=[119.0, 40.0, 132.0, 50.0])
>>> print(ndvi_ds)

>>> # 获取 2020 年地表反射率（500 m，MOD09A1）
>>> sr_ds = loader.load_surface_reflectance(year=2020, bbox=[119.0, 40.0, 132.0, 50.0])
>>> print(sr_ds)

>>> # 获取年度水体掩膜（250 m，MOD44W）
>>> water = loader.load_water_mask(year=2020, bbox=[119.0, 40.0, 132.0, 50.0])
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import xarray as xr

from config import (
    MODIS_NDVI_COLLECTION,
    MODIS_SR_COLLECTION,
    MODIS_WATER_COLLECTION,
    MODIS_SR_BANDS,
    MODIS_SR_SCALE_FACTOR,
    MODIS_NDVI_BANDS,
    MODIS_NDVI_SCALE_FACTOR,
    TARGET_CRS,
    GROWING_SEASON_MONTHS,
)
from src.data.stac_client import STACClient


class MODISLoader:
    """
    MODIS 数据加载器（基于 Planetary Computer STAC，懒加载，无需预下载）。

    Parameters
    ----------
    stac_client : STACClient, optional
        默认使用 Planetary Computer 客户端。
    """

    def __init__(self, stac_client: Optional[STACClient] = None) -> None:
        self.client = stac_client or STACClient.planetary_computer()

    # ──────────────────────────────────────────
    # MOD13Q1：NDVI/EVI 250 m，16 天合成
    # ──────────────────────────────────────────

    def load_ndvi(
        self,
        year: int,
        bbox: List[float],
        months: Optional[List[int]] = None,
        resolution: int = 250,
        crs: str = TARGET_CRS,
    ) -> xr.Dataset:
        """
        加载 MOD13Q1 NDVI/EVI 16 天合成产品。

        Parameters
        ----------
        year : int
        bbox : list of float  [west, south, east, north]
        months : list of int, optional  生长季月份，默认 GROWING_SEASON_MONTHS
        resolution : int  输出分辨率（米），默认 250 m
        crs : str

        Returns
        -------
        xr.Dataset
            变量：ndvi [−1,1]、evi [−1,1]、pixel_reliability (QC)
        """
        import stackstac

        months = months or GROWING_SEASON_MONTHS
        items = self.client.search_by_year(
            collections=[MODIS_NDVI_COLLECTION],
            bbox=bbox,
            year=year,
            months=months,
            max_cloud_cover=100,  # MODIS 自带 QC，不依赖 cloud_cover 字段
        )

        if not items:
            raise ValueError(
                f"未找到 {year} 年 MOD13Q1 数据（bbox={bbox}）。"
                "请检查 Planetary Computer STAC 连接。"
            )

        ndvi_band = MODIS_NDVI_BANDS["ndvi"]
        evi_band  = MODIS_NDVI_BANDS["evi"]
        qc_band   = MODIS_NDVI_BANDS["pixel_rel"]

        stack = stackstac.stack(
            items,
            assets=[ndvi_band, evi_band, qc_band],
            resolution=resolution,
            epsg=int(crs.split(":")[1]),
            bounds_latlon=bbox,
            fill_value=np.nan,
        )

        # 应用 QC 掩膜：pixel_reliability  0=好  1=边缘  2=雪/冰  3=云
        stack = self._apply_modis_ndvi_qc(stack, qc_band)

        # 重命名波段
        stack = stack.sel(band=[ndvi_band, evi_band])
        stack["band"] = ["ndvi", "evi"]

        # 缩放
        ds = stack.to_dataset(dim="band")
        ds["ndvi"] = (ds["ndvi"] * MODIS_NDVI_SCALE_FACTOR).clip(-1.0, 1.0)
        ds["evi"]  = (ds["evi"]  * MODIS_NDVI_SCALE_FACTOR).clip(-1.0, 1.0)

        ds["ndvi"].attrs = {"long_name": "MODIS NDVI (MOD13Q1)", "units": "dimensionless", "resolution_m": resolution}
        ds["evi"].attrs  = {"long_name": "MODIS EVI (MOD13Q1)",  "units": "dimensionless", "resolution_m": resolution}

        return ds

    # ──────────────────────────────────────────
    # MOD09A1：地表反射率 500 m，8 天合成
    # ──────────────────────────────────────────

    def load_surface_reflectance(
        self,
        year: int,
        bbox: List[float],
        months: Optional[List[int]] = None,
        resolution: int = 500,
        crs: str = TARGET_CRS,
    ) -> xr.Dataset:
        """
        加载 MOD09A1 地表反射率 8 天合成产品。

        返回波段：red, nir, blue, green, swir1, swir2
        可用于计算 NDWI 水体指数与补充 NDVI。

        Parameters
        ----------
        year : int
        bbox : list of float
        months : list of int, optional
        resolution : int  默认 500 m
        crs : str

        Returns
        -------
        xr.Dataset  反射率范围 [0, 1]
        """
        import stackstac

        months = months or GROWING_SEASON_MONTHS
        items = self.client.search_by_year(
            collections=[MODIS_SR_COLLECTION],
            bbox=bbox,
            year=year,
            months=months,
            max_cloud_cover=100,
        )

        if not items:
            raise ValueError(f"未找到 {year} 年 MOD09A1 数据（bbox={bbox}）。")

        sr_band_ids = [v for k, v in MODIS_SR_BANDS.items() if k != "qc"]
        qc_band_id  = MODIS_SR_BANDS["qc"]

        stack = stackstac.stack(
            items,
            assets=sr_band_ids + [qc_band_id],
            resolution=resolution,
            epsg=int(crs.split(":")[1]),
            bounds_latlon=bbox,
            fill_value=np.nan,
        )

        # 应用 QC 掩膜
        stack = self._apply_modis_sr_qc(stack, qc_band_id)

        # 只保留反射率波段并重命名
        std_names = [k for k in MODIS_SR_BANDS if k != "qc"]
        stack = stack.sel(band=sr_band_ids)
        stack["band"] = std_names

        ds = stack.to_dataset(dim="band")
        for var in std_names:
            ds[var] = (ds[var] * MODIS_SR_SCALE_FACTOR).clip(0.0, 1.0)
            ds[var].attrs = {"long_name": f"MODIS SR {var} (MOD09A1)", "units": "reflectance", "resolution_m": resolution}

        return ds

    # ──────────────────────────────────────────
    # MOD44W：年度水体掩膜 250 m
    # ──────────────────────────────────────────

    def load_water_mask(
        self,
        year: int,
        bbox: List[float],
        resolution: int = 250,
        crs: str = TARGET_CRS,
    ) -> xr.DataArray:
        """
        加载 MOD44W 年度水体掩膜（250 m）。

        Parameters
        ----------
        year : int
        bbox : list of float
        resolution : int  默认 250 m
        crs : str

        Returns
        -------
        xr.DataArray  bool 类型，True = 水体
        """
        import stackstac

        items = self.client.search(
            collections=[MODIS_WATER_COLLECTION],
            bbox=bbox,
            date_range=f"{year}-01-01/{year}-12-31",
            max_cloud_cover=100,
        )

        if not items:
            raise ValueError(f"未找到 {year} 年 MOD44W 水体掩膜数据（bbox={bbox}）。")

        # MOD44W 主波段为 "water_mask"
        water_asset = "water_mask"
        stack = stackstac.stack(
            items,
            assets=[water_asset],
            resolution=resolution,
            epsg=int(crs.split(":")[1]),
            bounds_latlon=bbox,
            fill_value=0,
        )

        # 取所有可用期次的最大值（年度内任一期为水即判为水）
        water = stack.sel(band=water_asset).max(dim="time") == 1

        water.attrs = {
            "long_name": "MODIS 年度水体掩膜 (MOD44W)",
            "year": year,
            "resolution_m": resolution,
        }
        return water

    # ──────────────────────────────────────────
    # 私有：QC 掩膜
    # ──────────────────────────────────────────

    @staticmethod
    def _apply_modis_ndvi_qc(
        stack: xr.DataArray,
        qc_band: str,
    ) -> xr.DataArray:
        """
        基于 MOD13Q1 pixel_reliability 波段过滤低质量像元。
          0 = Good data（保留）
          1 = Marginal data（保留）
          2 = Snow/Ice（剔除）
          3 = Cloudy（剔除）
        """
        if qc_band not in stack["band"].values:
            return stack

        qc = stack.sel(band=qc_band)
        bad = (qc == 2) | (qc == 3)
        return stack.where(~bad)

    @staticmethod
    def _apply_modis_sr_qc(
        stack: xr.DataArray,
        qc_band: str,
    ) -> xr.DataArray:
        """
        基于 MOD09A1 sur_refl_qc500m 波段过滤云/阴影像元。
        QC bit 0–1：00=理想质量，01=其他质量，10=云覆盖，11=云阴影
        """
        if qc_band not in stack["band"].values:
            return stack

        # 位运算要求整型；QC 波段存储为 float32，须先转换
        qc = stack.sel(band=qc_band).astype(int)
        cloud_mask = ((qc & 0b11) == 2) | ((qc & 0b11) == 3)
        return stack.where(~cloud_mask)
