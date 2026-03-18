"""
Landsat 数据获取模块
====================
基于 STAC API + stackstac 实现 Landsat 5/7/8/9 影像的懒加载读取，
无需预下载，按需计算。

支持传感器：
  - Landsat 5 TM  (1984–2013)
  - Landsat 7 ETM+ (1999–2022)
  - Landsat 8 OLI  (2013–至今)
  - Landsat 9 OLI-2 (2021–至今)

用法示例
--------
>>> from src.data.landsat import LandsatLoader
>>> loader = LandsatLoader()
>>> ds = loader.load_year(year=2020, bbox=[119.0, 40.0, 132.0, 50.0])
>>> ndvi = (ds["nir"] - ds["red"]) / (ds["nir"] + ds["red"])
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import xarray as xr

from config import (
    LANDSAT_COLLECTION_PC,
    LANDSAT_BANDS,
    LANDSAT_SCALE_FACTOR,
    LANDSAT_ADD_OFFSET,
    TARGET_RESOLUTION,
    TARGET_CRS,
    GROWING_SEASON_MONTHS,
    MAX_CLOUD_COVER,
)
from src.data.stac_client import STACClient


# Landsat 传感器 → Collection 2 platform 字段值
_PLATFORM_TO_SENSOR = {
    "landsat-5": "L5_L7",
    "landsat-7": "L5_L7",
    "landsat-8": "L8_L9",
    "landsat-9": "L8_L9",
}


def _get_sensor_key(item) -> str:
    """根据 STAC Item 属性判断传感器组（L5_L7 或 L8_L9）。"""
    platform = item.properties.get("platform", "").lower()
    for key, sensor_key in _PLATFORM_TO_SENSOR.items():
        if key in platform:
            return sensor_key
    # 默认按 Landsat 8/9 处理
    return "L8_L9"


class LandsatLoader:
    """
    Landsat Collection 2 Level-2 数据加载器。

    Parameters
    ----------
    stac_client : STACClient, optional
        STAC 客户端实例，默认使用 Planetary Computer。
    collection : str, optional
        Collection ID，默认 "landsat-c2-l2"。
    """

    def __init__(
        self,
        stac_client: Optional[STACClient] = None,
        collection: str = LANDSAT_COLLECTION_PC,
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
        加载指定年份的 Landsat 影像，返回统一波段命名的 xarray Dataset。

        Parameters
        ----------
        year : int
        bbox : list of float  [west, south, east, north]
        months : list of int, optional  生长季月份，默认 config.GROWING_SEASON_MONTHS
        max_cloud_cover : int
        resolution : int  输出分辨率（米）
        crs : str  输出坐标系

        Returns
        -------
        xr.Dataset
            包含波段：blue, green, red, nir, swir1, swir2
            时间维度为各影像获取时间，已进行反射率缩放。
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
                f"未找到 {year} 年云量 < {max_cloud_cover}% 的 Landsat 影像。"
                "请尝试增大 max_cloud_cover 或扩展搜索月份。"
            )

        # 按传感器类型分组，分别选取对应波段后合并
        groups: dict = {}
        for item in items:
            key = _get_sensor_key(item)
            groups.setdefault(key, []).append(item)

        arrays = []
        for sensor_key, group_items in groups.items():
            band_map = {
                std_name: aliases[sensor_key]
                for std_name, aliases in LANDSAT_BANDS.items()
                if std_name != "qa"
            }
            qa_band = LANDSAT_BANDS["qa"][sensor_key]

            # stackstac 懒加载（不会立即下载数据）
            stack = stackstac.stack(
                group_items,
                assets=list(band_map.values()) + [qa_band],
                resolution=resolution,
                epsg=int(crs.split(":")[1]),
                bounds_latlon=bbox,
                fill_value=np.nan,
            )

            # 重命名为标准波段名
            rename_map = {v: k for k, v in band_map.items()}
            rename_map[qa_band] = "qa"
            stack = stack.sel(band=list(rename_map.keys()))
            stack["band"] = [rename_map[b] for b in stack["band"].values]

            arrays.append(stack)

        # 合并不同传感器的数据并按时间排序
        if len(arrays) == 1:
            combined = arrays[0]
        else:
            combined = xr.concat(arrays, dim="time").sortby("time")

        # 应用云掩膜
        combined = self._apply_cloud_mask(combined)

        # 转换为反射率（排除 qa 波段）
        reflectance_bands = [b for b in combined["band"].values if b != "qa"]
        ref = combined.sel(band=reflectance_bands)
        ref = ref * LANDSAT_SCALE_FACTOR + LANDSAT_ADD_OFFSET
        ref = ref.clip(0.0, 1.0)

        return ref.to_dataset(dim="band")

    def _apply_cloud_mask(self, stack: xr.DataArray) -> xr.DataArray:
        """
        基于 QA_PIXEL 波段进行云掩膜。

        QA_PIXEL 位定义（Landsat Collection 2）：
          Bit 1 - Dilated Cloud
          Bit 3 - Cloud
          Bit 4 - Cloud Shadow
          Bit 5 - Snow

        Returns
        -------
        xr.DataArray  云像元已设为 NaN 的影像栈
        """
        if "qa" not in stack["band"].values:
            return stack

        qa = stack.sel(band="qa")
        # 标记云、云阴影像元
        cloud_mask = (
            ((qa & (1 << 1)) > 0)  # Dilated Cloud
            | ((qa & (1 << 3)) > 0)  # Cloud
            | ((qa & (1 << 4)) > 0)  # Cloud Shadow
        )

        # 将掩膜应用到所有波段
        masked = stack.where(~cloud_mask)
        return masked
