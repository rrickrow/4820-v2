# 松辽流域河道变迁与植被响应分析系统
# 全局配置文件
#
# 数据平台策略（无需 Google Earth Engine，无需预下载）：
#   主力数据：MODIS（NASA）via Planetary Computer STAC API  → 轻量（250–500 m）
#   气候数据：Open-Meteo 历史归档 REST API                  → 完全免费，无需账号
#   水体参考：JRC Global Surface Water                      → 直连瓦片/STAC
#   高分辨率补充（可选）：Sentinel-2 via Earth Search STAC  → 无需账号

# ──────────────────────────────────────────
# 研究区域：松辽流域（松花江 + 辽河）
# ──────────────────────────────────────────
STUDY_AREA_BBOX = [119.0, 40.0, 132.0, 50.0]  # [west, south, east, north] (WGS84)

# 松花江子流域
SONGHUA_BBOX = [123.0, 43.0, 132.0, 50.0]

# 辽河子流域
LIAOHE_BBOX = [119.0, 40.0, 125.0, 44.5]

# 研究区代表气象格点（用于 Open-Meteo 查询，松辽流域中心）
CLIMATE_POINT_LAT = 45.0
CLIMATE_POINT_LON = 125.5

# ──────────────────────────────────────────
# 时间范围
# ──────────────────────────────────────────
START_YEAR = 2000   # MODIS Terra 自 2000 年起；如需更早可叠加 AVHRR/NDVI3g
END_YEAR = 2024

# 无云影像筛选月份（生长季，避免冬季积雪影响）
GROWING_SEASON_MONTHS = [5, 6, 7, 8, 9]  # 5–9 月

# ──────────────────────────────────────────
# 主力数据：MODIS via Planetary Computer STAC（免费，无需账号，无需预下载）
# ──────────────────────────────────────────
PLANETARY_COMPUTER_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
USE_PLANETARY_COMPUTER_SIGNING = True

# MODIS Collection IDs（Planetary Computer）
MODIS_NDVI_COLLECTION = "modis-13Q1-061"   # MOD13Q1  NDVI/EVI 16-day  250 m
MODIS_SR_COLLECTION   = "modis-09A1-061"   # MOD09A1  Surface Reflectance 8-day 500 m
MODIS_WATER_COLLECTION = "modis-44W-061"   # MOD44W   Annual Water Mask 250 m

# ──────────────────────────────────────────
# 备选高分辨率数据（可选，仍免费无账号）
# Earth Search（AWS Element84）STAC，用于 Sentinel-2 补充验证
# ──────────────────────────────────────────
EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"
SENTINEL2_COLLECTION_ES = "sentinel-2-l2a"

# 兼容旧字段（timeseries 等模块仍引用）
DEFAULT_STAC_URL = PLANETARY_COMPUTER_URL

# ──────────────────────────────────────────
# 气候数据：Open-Meteo 历史归档 API（完全免费，无需账号，REST 直连）
# 文档：https://open-meteo.com/en/docs/historical-weather-api
# ──────────────────────────────────────────
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_DAILY_VARS = [
    "precipitation_sum",          # 日降水量（mm）
    "temperature_2m_max",         # 日最高气温（°C）
    "temperature_2m_min",         # 日最低气温（°C）
    "temperature_2m_mean",        # 日均气温（°C）
    "et0_fao_evapotranspiration", # 参考蒸散发（mm）
]
# Open-Meteo ERA5 数据从 1940 年起，最新约 5 天延迟
OPEN_METEO_START_DATE = "2000-01-01"

# ──────────────────────────────────────────
# 水体参考：JRC Global Surface Water（直连公共 COG 瓦片，免费，无需账号）
# ──────────────────────────────────────────
# JRC GSW 月度水体变化（Google Cloud Storage 公开存储，可直连）
JRC_GSW_BASE_URL = "https://storage.googleapis.com/global-surface-water/downloads2021"
JRC_GSW_RESOLUTION = 30   # 原生分辨率 30 m

# ──────────────────────────────────────────
# 影像处理参数
# ──────────────────────────────────────────
# MODIS 主力分辨率（250 m = MOD13Q1 NDVI；500 m = MOD09A1 地表反射率）
TARGET_RESOLUTION = 500       # 统一到 500 m（与 MOD09A1 一致）
MAX_CLOUD_COVER = 50          # MODIS 云量阈值（内置 QC 波段，允许适当放宽）
TARGET_CRS = "EPSG:32651"     # UTM Zone 51N，适合松辽流域

# ──────────────────────────────────────────
# MODIS MOD09A1 波段映射（500 m 表面反射率，8 天合成）
# ──────────────────────────────────────────
MODIS_SR_BANDS = {
    "red":   "sur_refl_b01",  # Band 1  620–670 nm
    "nir":   "sur_refl_b02",  # Band 2  841–876 nm
    "blue":  "sur_refl_b03",  # Band 3  459–479 nm
    "green": "sur_refl_b04",  # Band 4  545–565 nm
    "swir1": "sur_refl_b06",  # Band 6  1628–1652 nm
    "swir2": "sur_refl_b07",  # Band 7  2105–2155 nm
    "qc":    "sur_refl_qc500m",
}
MODIS_SR_SCALE_FACTOR = 0.0001   # DN × 0.0001 = 反射率

# MODIS MOD13Q1 波段映射（250 m NDVI/EVI，16 天合成）
MODIS_NDVI_BANDS = {
    "ndvi":       "250m_16_days_NDVI",
    "evi":        "250m_16_days_EVI",
    "red_refl":   "250m_16_days_red_reflectance",
    "nir_refl":   "250m_16_days_NIR_reflectance",
    "pixel_rel":  "250m_16_days_pixel_reliability",  # QC 标志
}
MODIS_NDVI_SCALE_FACTOR = 0.0001  # NDVI DN × 0.0001

# ──────────────────────────────────────────
# Sentinel-2 波段映射（兼容旧模块，可选）
# ──────────────────────────────────────────
SENTINEL2_COLLECTION_PC = "sentinel-2-l2a"
SENTINEL2_BANDS = {
    "blue":  "B02",
    "green": "B03",
    "red":   "B04",
    "nir":   "B08",
    "swir1": "B11",
    "swir2": "B12",
    "scl":   "SCL",
}
SENTINEL2_SCALE_FACTOR = 0.0001

# ──────────────────────────────────────────
# Landsat 波段映射（兼容旧模块，可选，已非主力数据源）
# ──────────────────────────────────────────
LANDSAT_COLLECTION_PC = "landsat-c2-l2"
LANDSAT_BANDS = {
    "blue":   {"L5_L7": "SR_B1", "L8_L9": "SR_B2"},
    "green":  {"L5_L7": "SR_B2", "L8_L9": "SR_B3"},
    "red":    {"L5_L7": "SR_B3", "L8_L9": "SR_B4"},
    "nir":    {"L5_L7": "SR_B4", "L8_L9": "SR_B5"},
    "swir1":  {"L5_L7": "SR_B5", "L8_L9": "SR_B6"},
    "swir2":  {"L5_L7": "SR_B7", "L8_L9": "SR_B7"},
    "qa":     {"L5_L7": "QA_PIXEL", "L8_L9": "QA_PIXEL"},
}
LANDSAT_SCALE_FACTOR = 0.0000275
LANDSAT_ADD_OFFSET = -0.2

# ──────────────────────────────────────────
# 水体 / 植被阈值
# ──────────────────────────────────────────
NDWI_THRESHOLD = 0.0          # NDWI > 0 判定为水体
NDVI_BARE_SOIL = 0.05         # NDVI 裸地阈值（NDVImin）
NDVI_FULL_COVER = 0.85        # NDVI 全覆盖阈值（NDVImax）

# ──────────────────────────────────────────
# 输出目录
# ──────────────────────────────────────────
OUTPUT_DIR = "outputs"
FIGURES_DIR = "outputs/figures"
REPORTS_DIR = "outputs/reports"
DATA_CACHE_DIR = "outputs/cache"
