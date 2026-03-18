"""
STAC API 统一客户端
===================
支持 Microsoft Planetary Computer 与 Earth Search（AWS Element84）两个免费平台，
均无需预下载影像，通过懒加载方式按需读取数据。

用法示例
--------
>>> from src.data.stac_client import STACClient
>>> client = STACClient()  # 默认使用 Planetary Computer
>>> items = client.search(
...     collections=["landsat-c2-l2"],
...     bbox=[119.0, 40.0, 132.0, 50.0],
...     date_range="2020-06-01/2020-09-30",
...     max_cloud_cover=20,
... )
>>> print(f"找到 {len(items)} 景影像")
"""

from __future__ import annotations

from typing import List, Optional

import pystac
import pystac_client

from config import (
    PLANETARY_COMPUTER_URL,
    EARTH_SEARCH_URL,
    DEFAULT_STAC_URL,
    USE_PLANETARY_COMPUTER_SIGNING,
    MAX_CLOUD_COVER,
)


class STACClient:
    """
    封装 pystac-client，统一处理 Planetary Computer 与 Earth Search 两种端点。

    Parameters
    ----------
    url : str, optional
        STAC API 端点 URL。默认使用 config.DEFAULT_STAC_URL。
    use_signing : bool, optional
        是否启用 Planetary Computer 资产签名。访问 PC 端点时须为 True。
    """

    def __init__(
        self,
        url: str = DEFAULT_STAC_URL,
        use_signing: bool = USE_PLANETARY_COMPUTER_SIGNING,
    ) -> None:
        self.url = url
        self.use_signing = use_signing
        self._client: Optional[pystac_client.Client] = None

    @property
    def client(self) -> pystac_client.Client:
        """懒初始化 STAC 客户端连接。"""
        if self._client is None:
            if self.use_signing:
                try:
                    import planetary_computer

                    self._client = pystac_client.Client.open(
                        self.url,
                        modifier=planetary_computer.sign_inplace,
                    )
                except ImportError as exc:
                    raise ImportError(
                        "planetary-computer 包未安装。"
                        "请运行: pip install planetary-computer"
                    ) from exc
            else:
                self._client = pystac_client.Client.open(self.url)
        return self._client

    def search(
        self,
        collections: List[str],
        bbox: List[float],
        date_range: str,
        max_cloud_cover: int = MAX_CLOUD_COVER,
        limit: int = 500,
    ) -> List[pystac.Item]:
        """
        搜索符合条件的 STAC Items。

        Parameters
        ----------
        collections : list of str
            Collection ID 列表，如 ["landsat-c2-l2"]。
        bbox : list of float
            [west, south, east, north]，WGS84 坐标。
        date_range : str
            日期范围，格式 "YYYY-MM-DD/YYYY-MM-DD"。
        max_cloud_cover : int
            最大云量（%）。
        limit : int
            最多返回景数。

        Returns
        -------
        list of pystac.Item
        """
        query = {}
        if max_cloud_cover < 100:
            query["eo:cloud_cover"] = {"lt": max_cloud_cover}

        search = self.client.search(
            collections=collections,
            bbox=bbox,
            datetime=date_range,
            query=query if query else None,
            max_items=limit,
        )
        items = list(search.items())
        return items

    def search_by_year(
        self,
        collections: List[str],
        bbox: List[float],
        year: int,
        months: Optional[List[int]] = None,
        max_cloud_cover: int = MAX_CLOUD_COVER,
    ) -> List[pystac.Item]:
        """
        按年份（及可选月份）搜索影像。

        Parameters
        ----------
        collections : list of str
        bbox : list of float
        year : int
        months : list of int, optional
            指定月份列表，如 [5, 6, 7, 8, 9] 表示生长季。
            若为 None，则搜索全年。
        max_cloud_cover : int

        Returns
        -------
        list of pystac.Item
        """
        if months:
            items: List[pystac.Item] = []
            for m in months:
                import calendar

                last_day = calendar.monthrange(year, m)[1]
                date_range = f"{year}-{m:02d}-01/{year}-{m:02d}-{last_day:02d}"
                items.extend(
                    self.search(collections, bbox, date_range, max_cloud_cover)
                )
            # 去重（同一 Item 可能被多月查询返回）
            seen: set = set()
            unique: List[pystac.Item] = []
            for item in items:
                if item.id not in seen:
                    seen.add(item.id)
                    unique.append(item)
            return unique
        else:
            date_range = f"{year}-01-01/{year}-12-31"
            return self.search(collections, bbox, date_range, max_cloud_cover)

    @classmethod
    def planetary_computer(cls) -> "STACClient":
        """创建指向 Microsoft Planetary Computer 的客户端。"""
        return cls(url=PLANETARY_COMPUTER_URL, use_signing=True)

    @classmethod
    def earth_search(cls) -> "STACClient":
        """创建指向 Earth Search（AWS Element84）的客户端。"""
        return cls(url=EARTH_SEARCH_URL, use_signing=False)
