"""
tests/test_climate.py
单元测试：Open-Meteo 气候 API 客户端

测试策略：
  - 纯单元测试（mock urllib.request.urlopen）：验证参数构造、数据解析逻辑
  - 集成测试（标记 @unittest.skipUnless）：需要网络，验证真实 API 响应
"""

import json
import sys
import os
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# 模拟 Open-Meteo API 返回的 JSON 结构
_MOCK_RESPONSE = {
    "latitude": 45.0,
    "longitude": 125.5,
    "daily": {
        "time": ["2020-06-01", "2020-06-02", "2020-06-03"],
        "precipitation_sum": [2.5, 0.0, 8.1],
        "temperature_2m_mean": [18.3, 19.1, 17.5],
        "temperature_2m_max": [24.0, 25.2, 22.8],
        "temperature_2m_min": [12.1, 13.0, 11.9],
        "et0_fao_evapotranspiration": [3.2, 3.5, 2.9],
    },
}


def _make_mock_urlopen(response_data: dict):
    """返回一个 mock context manager，模拟 urllib.request.urlopen 行为。"""
    raw = json.dumps(response_data).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = raw
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestOpenMeteoClientUnit(unittest.TestCase):
    """Open-Meteo 客户端纯单元测试（不联网）。"""

    @patch("urllib.request.urlopen")
    def test_get_daily_returns_dataframe(self, mock_urlopen):
        """get_daily() 应返回含正确列名的 DataFrame。"""
        mock_urlopen.return_value = _make_mock_urlopen(_MOCK_RESPONSE)

        from src.data.climate import OpenMeteoClient
        import pandas as pd

        client = OpenMeteoClient()
        df = client.get_daily(
            lat=45.0, lon=125.5,
            start="2020-06-01", end="2020-06-03",
            variables=["precipitation_sum", "temperature_2m_mean"],
        )

        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn("precipitation_sum", df.columns)
        self.assertIn("temperature_2m_mean", df.columns)
        self.assertEqual(len(df), 3)

    @patch("urllib.request.urlopen")
    def test_get_daily_index_is_datetime(self, mock_urlopen):
        """DataFrame 索引应为 datetime 类型。"""
        mock_urlopen.return_value = _make_mock_urlopen(_MOCK_RESPONSE)

        from src.data.climate import OpenMeteoClient
        import pandas as pd

        client = OpenMeteoClient()
        df = client.get_daily(lat=45.0, lon=125.5,
                              start="2020-06-01", end="2020-06-03")
        self.assertEqual(df.index.dtype.kind, "M",
                         "DataFrame 索引应为 DatetimeTZDtype 或 datetime64")

    @patch("urllib.request.urlopen")
    def test_get_annual_stats_aggregates_correctly(self, mock_urlopen):
        """get_annual_stats() 降水应取年总和，气温应取年均值。"""
        # 构造跨两年的模拟数据
        import pandas as pd

        mock_data = {
            "latitude": 45.0,
            "longitude": 125.5,
            "daily": {
                "time": ["2020-01-01", "2020-12-31", "2021-01-01", "2021-12-31"],
                "precipitation_sum": [5.0, 3.0, 2.0, 4.0],
                "temperature_2m_mean": [10.0, 20.0, 15.0, 25.0],
                "temperature_2m_max": [15.0, 28.0, 20.0, 30.0],
                "temperature_2m_min": [5.0, 12.0, 8.0, 18.0],
                "et0_fao_evapotranspiration": [1.0, 2.0, 1.5, 2.5],
            },
        }
        mock_urlopen.return_value = _make_mock_urlopen(mock_data)

        from src.data.climate import OpenMeteoClient

        client = OpenMeteoClient()
        annual = client.get_annual_stats(lat=45.0, lon=125.5,
                                         start_year=2020, end_year=2021)

        self.assertIn(2020, annual.index)
        self.assertIn(2021, annual.index)

        # 降水取年总和
        self.assertAlmostEqual(annual.loc[2020, "precipitation_sum"], 8.0, places=5)
        # 气温取年均值
        self.assertAlmostEqual(annual.loc[2020, "temperature_2m_mean"], 15.0, places=5)

    @patch("urllib.request.urlopen")
    def test_empty_response_raises_value_error(self, mock_urlopen):
        """当 API 返回空 daily 字段时，应抛出 ValueError。"""
        mock_urlopen.return_value = _make_mock_urlopen({"daily": {}})

        from src.data.climate import OpenMeteoClient

        client = OpenMeteoClient()
        with self.assertRaises(ValueError):
            client.get_daily(lat=0.0, lon=0.0, start="2020-01-01", end="2020-01-31")

    def test_default_url_is_archive(self):
        """默认 URL 应指向 Open-Meteo 历史归档端点。"""
        from src.data.climate import OpenMeteoClient
        from config import OPEN_METEO_ARCHIVE_URL

        client = OpenMeteoClient()
        self.assertEqual(client.base_url, OPEN_METEO_ARCHIVE_URL)
        self.assertIn("archive-api.open-meteo.com", client.base_url)

    @patch("urllib.request.urlopen")
    def test_url_contains_required_params(self, mock_urlopen):
        """发出的 HTTP 请求 URL 应包含 latitude、longitude、daily 等参数。"""
        mock_urlopen.return_value = _make_mock_urlopen(_MOCK_RESPONSE)

        from src.data.climate import OpenMeteoClient

        client = OpenMeteoClient()
        client.get_daily(lat=45.0, lon=125.5,
                         start="2020-06-01", end="2020-06-03",
                         variables=["precipitation_sum"])

        called_url = mock_urlopen.call_args[0][0]
        self.assertIn("latitude=45.0", called_url)
        self.assertIn("longitude=125.5", called_url)
        self.assertIn("start_date=2020-06-01", called_url)
        self.assertIn("precipitation_sum", called_url)


class TestOpenMeteoConfig(unittest.TestCase):
    """验证 Open-Meteo 相关配置存在且合理。"""

    def test_archive_url_defined(self):
        from config import OPEN_METEO_ARCHIVE_URL

        self.assertTrue(OPEN_METEO_ARCHIVE_URL.startswith("https://"),
                        "OPEN_METEO_ARCHIVE_URL 应以 https:// 开头")

    def test_daily_vars_not_empty(self):
        from config import OPEN_METEO_DAILY_VARS

        self.assertGreater(len(OPEN_METEO_DAILY_VARS), 0)
        self.assertIn("precipitation_sum", OPEN_METEO_DAILY_VARS)

    def test_climate_point_in_songliao_basin(self):
        """气候格点应位于松辽流域范围内。"""
        from config import CLIMATE_POINT_LAT, CLIMATE_POINT_LON, STUDY_AREA_BBOX

        west, south, east, north = STUDY_AREA_BBOX
        self.assertTrue(south <= CLIMATE_POINT_LAT <= north,
                        f"纬度 {CLIMATE_POINT_LAT} 不在研究区范围 [{south}, {north}]")
        self.assertTrue(west <= CLIMATE_POINT_LON <= east,
                        f"经度 {CLIMATE_POINT_LON} 不在研究区范围 [{west}, {east}]")


if __name__ == "__main__":
    unittest.main()
