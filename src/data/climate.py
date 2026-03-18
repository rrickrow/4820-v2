"""
Open-Meteo 气候数据模块
========================
通过 **Open-Meteo 历史归档 REST API** 获取逐日气候数据。

特点：
  - 完全免费，无需账号，无需任何 API Key
  - 数据覆盖 1940 年至今（ERA5 再分析）
  - 支持任意经纬度格点，适合松辽流域多站点查询
  - 无需预下载，直接返回 pandas DataFrame

API 文档：https://open-meteo.com/en/docs/historical-weather-api

支持变量（本项目使用）：
  - precipitation_sum          日降水量（mm）
  - temperature_2m_mean        日均气温（°C）
  - temperature_2m_max/min     日最高/最低气温（°C）
  - et0_fao_evapotranspiration 参考蒸散发（mm）

用法示例
--------
>>> from src.data.climate import OpenMeteoClient
>>> client = OpenMeteoClient()

>>> # 获取松辽流域代表点 2000–2023 年逐日降水
>>> df = client.get_daily(lat=45.0, lon=125.5, start="2000-01-01", end="2023-12-31")
>>> print(df.head())

>>> # 获取年均降水量时序
>>> annual = client.get_annual_stats(lat=45.0, lon=125.5, start_year=2000, end_year=2023)
>>> print(annual)
"""

from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import urlencode

import pandas as pd

from config import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_DAILY_VARS,
    CLIMATE_POINT_LAT,
    CLIMATE_POINT_LON,
)


class OpenMeteoClient:
    """
    Open-Meteo 历史归档 API 客户端。

    完全免费，无需账号，通过 HTTP GET 请求直接获取数据，
    返回格式为 pandas DataFrame（无需下载任何文件）。

    Parameters
    ----------
    base_url : str
        API 端点，默认使用 config.OPEN_METEO_ARCHIVE_URL。
    timeout : int
        HTTP 请求超时（秒），默认 30。
    """

    def __init__(
        self,
        base_url: str = OPEN_METEO_ARCHIVE_URL,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def get_daily(
        self,
        lat: float = CLIMATE_POINT_LAT,
        lon: float = CLIMATE_POINT_LON,
        start: str = "2000-01-01",
        end: str = "2023-12-31",
        variables: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取指定格点的逐日气候数据。

        Parameters
        ----------
        lat : float  纬度
        lon : float  经度
        start : str  起始日期（YYYY-MM-DD）
        end : str    截止日期（YYYY-MM-DD）
        variables : list of str, optional
            需要查询的气候变量，默认使用 config.OPEN_METEO_DAILY_VARS

        Returns
        -------
        pd.DataFrame
            index = datetime，columns = 气候变量名
        """
        import urllib.request
        import json

        if variables is None:
            variables = OPEN_METEO_DAILY_VARS

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "daily": ",".join(variables),
            "timezone": "Asia/Shanghai",
        }
        url = f"{self.base_url}?{urlencode(params)}"

        with urllib.request.urlopen(url, timeout=self.timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))

        daily = data.get("daily", {})
        if not daily or "time" not in daily:
            raise ValueError(
                f"Open-Meteo API 返回空数据。请检查参数：lat={lat}, lon={lon}, "
                f"start={start}, end={end}"
            )

        df = pd.DataFrame(daily)
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
        df.index.name = "date"

        return df

    def get_annual_stats(
        self,
        lat: float = CLIMATE_POINT_LAT,
        lon: float = CLIMATE_POINT_LON,
        start_year: int = 2000,
        end_year: int = 2023,
        variables: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取逐年气候统计（年均值 / 年总量）。

        Parameters
        ----------
        lat, lon : float
        start_year, end_year : int
        variables : list of str, optional

        Returns
        -------
        pd.DataFrame
            index = year（int），columns = 变量统计值
            - precipitation_sum → 年总降水（mm）
            - temperature_*     → 年均气温（°C）
            - et0_*             → 年总蒸散发（mm）
        """
        if variables is None:
            variables = OPEN_METEO_DAILY_VARS

        df_daily = self.get_daily(
            lat=lat, lon=lon,
            start=f"{start_year}-01-01",
            end=f"{end_year}-12-31",
            variables=variables,
        )

        # 按年聚合
        df_daily["year"] = df_daily.index.year
        agg_rules: Dict[str, str] = {}
        for col in df_daily.columns:
            if col == "year":
                continue
            if "sum" in col or "precipitation" in col or "et0" in col:
                agg_rules[col] = "sum"    # 累积量取年总和
            else:
                agg_rules[col] = "mean"   # 气温取年均值

        annual = df_daily.groupby("year").agg(agg_rules)
        annual.index.name = "year"
        return annual

    def get_multi_point_annual(
        self,
        points: List[Dict[str, float]],
        start_year: int = 2000,
        end_year: int = 2023,
        variables: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取多格点的年度气候数据（对应水文年鉴站点）。

        Parameters
        ----------
        points : list of dict
            [{"name": "站点名", "lat": 45.0, "lon": 125.5}, ...]
        start_year, end_year : int
        variables : list of str, optional

        Returns
        -------
        dict  {站点名: annual_stats_DataFrame}
        """
        results: Dict[str, pd.DataFrame] = {}
        for pt in points:
            name = pt.get("name", f"pt_{pt['lat']}_{pt['lon']}")
            try:
                df = self.get_annual_stats(
                    lat=pt["lat"],
                    lon=pt["lon"],
                    start_year=start_year,
                    end_year=end_year,
                    variables=variables,
                )
                results[name] = df
                print(f"  ✓ {name} ({pt['lat']}°N, {pt['lon']}°E): {len(df)} 年数据")
            except Exception as e:
                print(f"  ✗ {name} 查询失败: {e}")
        return results
