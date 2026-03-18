"""
Sentinel-2 数据获取模块
========================
基于 STAC API + stackstac 实现 Sentinel-2 L2A 表面反射率影像的懒加载读取。

特点：
  - 10 m 分辨率（B02/B03/B04/B08），可重采样至 30 m 与 Landsat 配准
  - 使用 SCL（Scene Classification Layer）进行精细云掩膜
  - 适合高分辨率植被覆盖度（FVC）分析

用法示例
--------
>>> from src.data.sentinel2 import Sentinel2Loader
>>> loader = Sentinel2Loader()
>>> ds = loader.load_year(year=2022, bbox=[119.0, 40.0, 132.0, 50.0])
>>> ndvi = (ds["nir"] - ds["red"]) / (ds["nir"] + ds["red"])
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import xarray as xr

from config import (
    SENTINEL2_COLLECTION_PC,
    SENTINEL2_BANDS,
    SENTINEL2_SCALE_FACTOR,
    TARGET_RESOLUTION,
    TARGET_CRS,
    GROWING_SEASON_MONTHS,
    MAX_CLOUD_COVER,
)
from src.data.stac_client import STACClient

# Sentinel-2 SCL 类别值（用于云掩膜）
# 参考：https://sentinels.copernicus.eu/web/sentinel/technical-guides/sentinel-2-msi/level-2a/algorithm
_SCL_CLOUD_VALUES = {3, 8, 9, 10, 11}  # Cloud shadows=3, Med/High/Thin clouds=8,9,10, Snow/Ice=11


class Sentinel2Loader:
    """
    Sentinel-2 Level-2A 数据加载器。

    Parameters
    ----------
    stac_client : STACClient, optional
        STAC 客户端实例，默认使用 Planetary Computer。
    collection : str, optional
        Collection ID，默认 "sentinel-2-l2a"。
    """

    def __init__(
        self,
        stac_client: Optional[STACClient] = None,
        collection: str = SENTINEL2_COLLECTION_PC,
    ) -> None:
        self.client = stac_client or STACClient.planetary_computer()
        self.collection = collection

    def load_year(
        self,
        year: int,
        bbox: List[float],
        months: Optional[List[int]] = None,
        max_cloud_cover: int = MAX_CLOUD_COVER,
        resolution: int = TARGET_RESOLUTION,
        crs: str = TARGET_CRS,
    ) -> xr.Dataset:
        """
        加载指定年份的 Sentinel-2 L2A 影像，返回统一波段命名的 xarray Dataset。

        Parameters
        ----------
        year : int
        bbox : list of float  [west, south, east, north]
        months : list of int, optional
        max_cloud_cover : int
        resolution : int  输出分辨率（米），默认 30 m（与 Landsat 统一）
        crs : str

        Returns
        -------
        xr.Dataset
            包含波段：blue, green, red, nir, swir1, swir2
            反射率范围 [0, 1]。
        """
        import stackstac

        if months is None:
            months = GROWING_SEASON_MONTHS

        items = self.client.search_by_year(
            collections=[self.collection],
            bbox=bbox,
            year=year,
            months=months,
            max_cloud_cover=max_cloud_cover,
        )

        if not items:
            raise ValueError(
                f"未找到 {year} 年云量 < {max_cloud_cover}% 的 Sentinel-2 影像。"
            )

        # 选取所需波段
        reflectance_bands = {k: v for k, v in SENTINEL2_BANDS.items() if k != "scl"}
        scl_band = SENTINEL2_BANDS["scl"]
        all_band_ids = list(reflectance_bands.values()) + [scl_band]

        stack = stackstac.stack(
            items,
            assets=all_band_ids,
            resolution=resolution,
            epsg=int(crs.split(":")[1]),
            bounds_latlon=bbox,
            fill_value=np.nan,
        )

        # 重命名为标准波段名
        rename_map = {v: k for k, v in reflectance_bands.items()}
        rename_map[scl_band] = "scl"
        stack = stack.sel(band=list(rename_map.keys()))
        stack["band"] = [rename_map[b] for b in stack["band"].values]

        # 应用 SCL 云掩膜
        stack = self._apply_scl_mask(stack)

        # 转换为反射率
        ref_bands = [b for b in stack["band"].values if b != "scl"]
        ref = stack.sel(band=ref_bands)
        ref = ref * SENTINEL2_SCALE_FACTOR
        ref = ref.clip(0.0, 1.0)

        return ref.to_dataset(dim="band")

    def _apply_scl_mask(self, stack: xr.DataArray) -> xr.DataArray:
        """
        使用 SCL（Scene Classification Layer）进行精细云/雪掩膜。

        SCL 值说明：
          0  - No data
          1  - Saturated / Defective
          2  - Dark Area Pixels
          3  - Cloud Shadows
          4  - Vegetation
          5  - Bare Soils
          6  - Water
          7  - Low Probability Clouds
          8  - Medium Probability Clouds
          9  - High Probability Clouds
          10 - Thin Cirrus
          11 - Snow / Ice

        Returns
        -------
        xr.DataArray
        """
        if "scl" not in stack["band"].values:
            return stack

        scl = stack.sel(band="scl")
        cloud_mask = xr.zeros_like(scl, dtype=bool)
        for val in _SCL_CLOUD_VALUES:
            cloud_mask = cloud_mask | (scl == val)

        masked = stack.where(~cloud_mask)
        return masked
