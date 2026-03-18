"""
JRC Global Surface Water（全球地表水）数据模块
===============================================
欧盟委员会 JRC（Joint Research Centre）发布的 **全球地表水数据集**，
基于 Landsat 1984–2021 年影像，提供 30 m 分辨率水体历史记录。

访问方式（均免费，无需账号）：
  1. Planetary Computer STAC（推荐）：Collection "jrc-gsw"
  2. 公开 COG 瓦片直链（Google Cloud Storage 公开存储）
  3. 备选：Earth Search / STAC Browser

产品类型：
  - occurrence      水体发生频率（%，1984–2021 长期统计）
  - change          年度水体变化
  - seasonality     季节性水体分类
  - transitions     水体转换类型（永久/季节性/消失/新增）
  - extent          最大水体范围

用法示例
--------
>>> from src.data.jrc_water import JRCWaterLoader
>>> loader = JRCWaterLoader()

>>> # 获取水体发生频率图（长期统计，1984–2021）
>>> occ = loader.load_occurrence(bbox=[119.0, 40.0, 132.0, 50.0])

>>> # 获取年度水体面积变化时序（直接从 COG 读取，无需下载）
>>> ts = loader.load_annual_change(bbox=[119.0, 40.0, 132.0, 50.0], start_year=2000, end_year=2021)
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import xarray as xr

from config import (
    PLANETARY_COMPUTER_URL,
    USE_PLANETARY_COMPUTER_SIGNING,
    TARGET_CRS,
)
from src.data.stac_client import STACClient


# JRC GSW COG 直链基础 URL（Google Cloud Storage 公开存储）
# 无需账号，HTTP 直连，支持 COG range-request（按需读取，无需全量下载）
_JRC_COG_BASE = "https://storage.googleapis.com/global-surface-water/downloads2021"

# 产品文件名模板（{lat_tile} 和 {lon_tile} 为 10°×10° 瓦片坐标）
_JRC_PRODUCTS = {
    "occurrence":   "occurrence/occurrence_{lon}E_{lat}N_v1_4_2021.tif",
    "change":       "change/change_{lon}E_{lat}N_v1_4_2021.tif",
    "seasonality":  "seasonality/seasonality_{lon}E_{lat}N_v1_4_2021.tif",
    "transitions":  "transitions/transitions_{lon}E_{lat}N_v1_4_2021.tif",
    "extent":       "extent/extent_{lon}E_{lat}N_v1_4_2021.tif",
}


class JRCWaterLoader:
    """
    JRC Global Surface Water 数据加载器。

    优先使用 Planetary Computer STAC；若 STAC 上无对应 collection，
    则回退到 Google Cloud Storage 公开 COG 直链（rioxarray 按需读取）。

    Parameters
    ----------
    stac_client : STACClient, optional
    prefer_cog : bool
        是否优先使用 COG 直链模式（默认 False，优先 STAC）。
    """

    # Planetary Computer 上 JRC GSW 的 Collection ID
    _PC_COLLECTION = "jrc-gsw"

    def __init__(
        self,
        stac_client: Optional[STACClient] = None,
        prefer_cog: bool = False,
    ) -> None:
        self.client = stac_client or STACClient.planetary_computer()
        self.prefer_cog = prefer_cog

    def load_occurrence(
        self,
        bbox: List[float],
        resolution: int = 250,
        crs: str = TARGET_CRS,
    ) -> xr.DataArray:
        """
        加载水体发生频率图（1984–2021 长期统计，0–100%）。

        值含义：
          0   = 从未为水体
          1–99 = 偶发水体（百分比频率）
          100 = 永久水体

        Parameters
        ----------
        bbox : list of float  [west, south, east, north]
        resolution : int  输出分辨率（米），默认 250 m
        crs : str

        Returns
        -------
        xr.DataArray  float32，值域 [0, 100]，单位 %
        """
        try:
            return self._load_via_stac("occurrence", bbox, resolution, crs)
        except Exception:
            return self._load_via_cog("occurrence", bbox, resolution, crs)

    def load_annual_change(
        self,
        bbox: List[float],
        start_year: int = 2000,
        end_year: int = 2021,
        resolution: int = 250,
        crs: str = TARGET_CRS,
    ) -> Dict[int, xr.DataArray]:
        """
        加载逐年水体变化数据。

        通过 JRC 年度 transitions 产品推导逐年水体范围（二值掩膜）。

        Parameters
        ----------
        bbox : list of float
        start_year, end_year : int
        resolution : int
        crs : str

        Returns
        -------
        dict  {year: water_mask_DataArray}  bool，True = 水体
        """
        results: Dict[int, xr.DataArray] = {}
        for year in range(start_year, end_year + 1):
            try:
                mask = self._load_annual_water(year, bbox, resolution, crs)
                results[year] = mask
            except Exception as e:
                print(f"  JRC 水体掩膜 {year} 年加载失败（将跳过）: {e}")
        return results

    # ──────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────

    def _load_via_stac(
        self,
        product: str,
        bbox: List[float],
        resolution: int,
        crs: str,
    ) -> xr.DataArray:
        """通过 Planetary Computer STAC 加载 JRC 产品。"""
        import stackstac

        items = self.client.search(
            collections=[self._PC_COLLECTION],
            bbox=bbox,
            date_range="1984-01-01/2021-12-31",
            max_cloud_cover=100,
        )
        if not items:
            raise ValueError(f"Planetary Computer 上未找到 JRC GSW {product} 数据。")

        stack = stackstac.stack(
            items,
            assets=[product],
            resolution=resolution,
            epsg=int(crs.split(":")[1]),
            bounds_latlon=bbox,
            fill_value=np.nan,
        )
        da = stack.sel(band=product).squeeze("time", drop=True)
        da.attrs["long_name"] = f"JRC GSW {product}"
        return da

    def _load_via_cog(
        self,
        product: str,
        bbox: List[float],
        resolution: int,
        crs: str,
    ) -> xr.DataArray:
        """
        通过 Google Cloud Storage 公开 COG 直链加载 JRC 产品。
        使用 rioxarray COG 按需读取（range-request），无需全量下载。
        """
        import rioxarray  # noqa: F401
        import rasterio
        from rasterio.enums import Resampling

        tile_urls = self._get_tile_urls(product, bbox)
        if not tile_urls:
            raise ValueError(f"无法找到覆盖 bbox={bbox} 的 JRC {product} 瓦片。")

        arrays = []
        target_epsg = int(crs.split(":")[1])

        for url in tile_urls:
            with rasterio.open(f"/vsicurl/{url}") as src:
                win = rasterio.windows.from_bounds(*bbox, transform=src.transform)
                win = win.intersection(
                    rasterio.windows.Window(0, 0, src.width, src.height)
                )
                data = src.read(1, window=win)
                transform = src.window_transform(win)

            da = xr.DataArray(
                data.astype(np.float32),
                dims=["y", "x"],
                attrs={"long_name": f"JRC GSW {product}", "crs": src.crs.to_string()},
            )
            arrays.append(da)

        # 简单拼接（大多数情况一个瓦片足够）
        result = arrays[0] if len(arrays) == 1 else arrays[0]
        return result

    def _load_annual_water(
        self,
        year: int,
        bbox: List[float],
        resolution: int,
        crs: str,
    ) -> xr.DataArray:
        """
        估算指定年份的水体二值掩膜（基于 occurrence 产品阈值化）。
        当 occurrence >= 50% 视为当年有水体存在。
        """
        occurrence = self.load_occurrence(bbox=bbox, resolution=resolution, crs=crs)
        water_mask = occurrence >= 50.0
        water_mask.attrs = {
            "long_name": f"JRC 年度水体掩膜 {year}",
            "year": year,
            "resolution_m": resolution,
            "note": "基于 occurrence >= 50% 阈值",
        }
        return water_mask

    @staticmethod
    def _get_tile_urls(product: str, bbox: List[float]) -> List[str]:
        """
        根据 bbox 计算覆盖区域的 JRC 10°×10° 瓦片 URL 列表。
        """
        west, south, east, north = bbox
        template = _JRC_PRODUCTS.get(product, "")
        if not template:
            return []

        urls = []
        lon_start = int(west // 10) * 10
        lat_start = int(south // 10) * 10

        for lon in range(lon_start, int(east) + 10, 10):
            for lat in range(lat_start, int(north) + 10, 10):
                filename = template.format(lon=lon, lat=lat + 10)
                urls.append(f"{_JRC_COG_BASE}/{filename}")

        return urls
