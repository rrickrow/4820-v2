# 松辽流域河道变迁与植被响应分析系统
# 全局配置文件

# ──────────────────────────────────────────
# 研究区域：松辽流域（松花江 + 辽河）
# ──────────────────────────────────────────
STUDY_AREA_BBOX = [119.0, 40.0, 132.0, 50.0]  # [west, south, east, north] (WGS84)

# 松花江子流域
SONGHUA_BBOX = [123.0, 43.0, 132.0, 50.0]

# 辽河子流域
LIAOHE_BBOX = [119.0, 40.0, 125.0, 44.5]

# ──────────────────────────────────────────
# 时间范围
# ──────────────────────────────────────────
START_YEAR = 1995
END_YEAR = 2025

# 无云影像筛选月份（生长季，避免冬季积雪影响）
GROWING_SEASON_MONTHS = [5, 6, 7, 8, 9]  # 5–9 月

# ──────────────────────────────────────────
# STAC API 端点（免费，无需账号）
# ──────────────────────────────────────────
PLANETARY_COMPUTER_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"

# 默认使用 Planetary Computer；Earth Search 作为备选
DEFAULT_STAC_URL = PLANETARY_COMPUTER_URL
USE_PLANETARY_COMPUTER_SIGNING = True  # Planetary Computer 需要对资产 URL 签名

# ──────────────────────────────────────────
# Collection IDs
# ──────────────────────────────────────────
LANDSAT_COLLECTION_PC = "landsat-c2-l2"       # Planetary Computer
SENTINEL2_COLLECTION_PC = "sentinel-2-l2a"    # Planetary Computer
LANDSAT_COLLECTION_ES = "landsat-c2-l2"       # Earth Search
SENTINEL2_COLLECTION_ES = "sentinel-2-l2a"    # Earth Search

# ──────────────────────────────────────────
# 影像处理参数
# ──────────────────────────────────────────
TARGET_RESOLUTION = 30        # 统一空间分辨率（米），与 Landsat 一致
MAX_CLOUD_COVER = 30          # 最大云量百分比（%）
TARGET_CRS = "EPSG:32651"     # UTM Zone 51N，适合松辽流域

# ──────────────────────────────────────────
# Landsat 波段映射（Collection 2 Level-2 表面反射率）
# ──────────────────────────────────────────
LANDSAT_BANDS = {
    "blue":   {"L5_L7": "SR_B1", "L8_L9": "SR_B2"},
    "green":  {"L5_L7": "SR_B2", "L8_L9": "SR_B3"},
    "red":    {"L5_L7": "SR_B3", "L8_L9": "SR_B4"},
    "nir":    {"L5_L7": "SR_B4", "L8_L9": "SR_B5"},
    "swir1":  {"L5_L7": "SR_B5", "L8_L9": "SR_B6"},
    "swir2":  {"L5_L7": "SR_B7", "L8_L9": "SR_B7"},
    "qa":     {"L5_L7": "QA_PIXEL", "L8_L9": "QA_PIXEL"},
}

# Landsat Collection 2 表面反射率缩放因子
LANDSAT_SCALE_FACTOR = 0.0000275
LANDSAT_ADD_OFFSET = -0.2

# ──────────────────────────────────────────
# Sentinel-2 波段映射（L2A 表面反射率）
# ──────────────────────────────────────────
SENTINEL2_BANDS = {
    "blue":  "B02",
    "green": "B03",
    "red":   "B04",
    "nir":   "B08",
    "swir1": "B11",
    "swir2": "B12",
    "scl":   "SCL",   # Scene Classification Layer（用于云掩膜）
}

# Sentinel-2 反射率缩放（DN / 10000 = 反射率）
SENTINEL2_SCALE_FACTOR = 0.0001

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
