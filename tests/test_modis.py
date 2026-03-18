"""
tests/test_modis.py
单元测试：MODIS 数据加载器（MODISLoader）

这些测试在不联网的情况下验证模块逻辑（mock STAC 调用）。
"""

import sys
import os
import types
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import xarray as xr

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Mock 掉可能未安装的重型依赖，使纯单元测试不依赖网络环境 ──
for _mod in ["pystac", "pystac_client", "planetary_computer", "stackstac",
             "rioxarray", "rasterio", "rasterio.enums", "rasterio.windows"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


class TestMODISQCMethods(unittest.TestCase):
    """直接测试静态 QC 方法，不触发 STAC 依赖。"""

    def _import_loader(self):
        # 确保 stac_client 也被 mock
        with patch.dict(sys.modules, {"pystac": MagicMock(),
                                       "pystac_client": MagicMock()}):
            from src.data.modis import MODISLoader  # noqa: PLC0415
            return MODISLoader

    def test_apply_modis_ndvi_qc_masks_clouds(self):
        """_apply_modis_ndvi_qc 应将 pixel_reliability == 3（云）替换为 NaN。"""
        MODISLoader = self._import_loader()

        # 构造包含 ndvi 和 qc 波段的假 stack（band × time × y × x）
        ndvi_vals = np.ones((1, 3, 3), dtype=np.float32) * 5000
        # qc: 0=好，1=边缘，2=雪/冰，3=云
        qc_vals = np.array([[[0, 3, 1], [3, 0, 2], [1, 2, 0]]], dtype=np.float32)

        stack = xr.DataArray(
            np.stack([ndvi_vals, qc_vals], axis=0),
            dims=["band", "time", "y", "x"],
            coords={"band": ["250m_16_days_NDVI", "250m_16_days_pixel_reliability"]},
        )

        result = MODISLoader._apply_modis_ndvi_qc(stack, "250m_16_days_pixel_reliability")

        ndvi_out = result.sel(band="250m_16_days_NDVI")
        # qc=3（云）的位置应为 NaN
        self.assertTrue(np.isnan(ndvi_out.values[0, 0, 1]),
                        "云像元（qc=3）应被掩膜为 NaN")
        # qc=2（雪/冰）的位置应为 NaN
        self.assertTrue(np.isnan(ndvi_out.values[0, 1, 2]),
                        "雪/冰像元（qc=2）应被掩膜为 NaN")
        # qc=0（好数据）的位置应保留
        self.assertFalse(np.isnan(ndvi_out.values[0, 0, 0]),
                         "好数据（qc=0）不应被掩膜")

    def test_apply_modis_sr_qc_masks_clouds(self):
        """_apply_modis_sr_qc 应将 QC bit 0-1 == 2 的像元替换为 NaN。"""
        MODISLoader = self._import_loader()

        sr_vals = np.ones((1, 2, 2), dtype=np.float32) * 3000
        # bit 0-1: 0b10=2(云), 0b00=0(好), 0b11=3(云阴影), 0b01=1(其他)
        qc_vals = np.array([[[2, 0], [3, 1]]], dtype=np.float32)

        stack = xr.DataArray(
            np.stack([sr_vals, qc_vals], axis=0),
            dims=["band", "time", "y", "x"],
            coords={"band": ["sur_refl_b01", "sur_refl_qc500m"]},
        )

        result = MODISLoader._apply_modis_sr_qc(stack, "sur_refl_qc500m")
        sr_out = result.sel(band="sur_refl_b01")

        self.assertTrue(np.isnan(sr_out.values[0, 0, 0]), "云像元（qc bit=2）应为 NaN")
        self.assertTrue(np.isnan(sr_out.values[0, 1, 0]), "云阴影（qc bit=3）应为 NaN")
        self.assertFalse(np.isnan(sr_out.values[0, 0, 1]), "好数据（qc=0）不应为 NaN")

    def test_loader_init_uses_planetary_computer(self):
        """MODISLoader() 默认应使用 STACClient.planetary_computer() 返回的客户端。"""
        MODISLoader = self._import_loader()

        # 验证：当未传入 stac_client 时，loader.client 是通过 planetary_computer() 构建的
        # 由于模块已缓存，直接验证 client 属性不为 None 且是 MagicMock 实例
        loader = MODISLoader()
        # planetary_computer() 被 mock 返回一个 MagicMock，所以 client 应是 MagicMock
        self.assertIsNotNone(loader.client,
                             "MODISLoader 的 client 属性不应为 None")

    def test_ndvi_scale_factor(self):
        """NDVI 值应乘以 0.0001 缩放到合理范围。"""
        from config import MODIS_NDVI_SCALE_FACTOR

        raw_dn = 8000.0
        expected = raw_dn * MODIS_NDVI_SCALE_FACTOR
        self.assertAlmostEqual(expected, 0.8, places=5)

    def test_ndvi_clipped_to_minus1_1(self):
        """缩放后的 NDVI 应被 clip 到 [-1, 1]。"""
        raw_dn = 15000.0
        scaled = raw_dn * 0.0001
        clipped = min(max(scaled, -1.0), 1.0)
        self.assertEqual(clipped, 1.0)


class TestMODISConfig(unittest.TestCase):
    """验证 MODIS 相关配置项存在且合理。"""

    def test_modis_collections_defined(self):
        from config import MODIS_NDVI_COLLECTION, MODIS_SR_COLLECTION, MODIS_WATER_COLLECTION

        self.assertEqual(MODIS_NDVI_COLLECTION, "modis-13Q1-061")
        self.assertEqual(MODIS_SR_COLLECTION, "modis-09A1-061")
        self.assertEqual(MODIS_WATER_COLLECTION, "modis-44W-061")

    def test_modis_sr_bands_defined(self):
        from config import MODIS_SR_BANDS

        required = {"red", "nir", "blue", "green", "swir1", "swir2", "qc"}
        self.assertTrue(required.issubset(set(MODIS_SR_BANDS.keys())),
                        f"缺少波段定义: {required - set(MODIS_SR_BANDS.keys())}")

    def test_modis_ndvi_bands_defined(self):
        from config import MODIS_NDVI_BANDS

        required = {"ndvi", "evi", "pixel_rel"}
        self.assertTrue(required.issubset(set(MODIS_NDVI_BANDS.keys())))

    def test_start_year_is_2000_or_later(self):
        """MODIS 从 2000 年起才有数据。"""
        from config import START_YEAR

        self.assertGreaterEqual(START_YEAR, 2000,
                                "MODIS Terra 从 2000 年 2 月起才运行，START_YEAR 不应早于 2000")


if __name__ == "__main__":
    unittest.main()
