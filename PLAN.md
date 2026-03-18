# 松辽流域河道变迁与植被响应分析系统 — 工程计划书

> **项目名称**：从遥感视角揭示过去三十年松辽流域河道变迁及其对周围植被的影响  
> **数据平台**：MODIS (NASA) via Planetary Computer STAC + Open-Meteo REST API + JRC GSW  
> **核心优势**：免费直连、无需 Google/GEE 账号、无需预下载、数据量轻量（250–500 m）

---

## 一、整体架构

```
songliao-analysis/
├── PLAN.md                       # 本计划书
├── README.md                     # 项目说明
├── requirements.txt              # Python 依赖
├── config.py                     # 全局配置（研究区、时间范围、参数）
├── src/
│   ├── data/
│   │   ├── stac_client.py        # STAC API 统一客户端（Planetary Computer / Earth Search）
│   │   ├── modis.py              # ★ MODIS 主力数据（MOD13Q1/MOD09A1/MOD44W，懒加载）
│   │   ├── climate.py            # ★ Open-Meteo 气候 API（降水、气温，无账号）
│   │   ├── jrc_water.py          # ★ JRC Global Surface Water（水体历史，COG 直连）
│   │   ├── landsat.py            # Landsat（可选，已非主力）
│   │   └── sentinel2.py          # Sentinel-2（可选高分辨率补充）
│   ├── processing/
│   │   ├── preprocessing.py      # 云掩膜、辐射归一化、年度合成
│   │   ├── fusion.py             # 多传感器融合（可选）
│   │   └── timeseries.py         # ★ 长时序构建（基于 MODIS，2000–2024）
│   ├── analysis/
│   │   ├── ndwi.py               # NDWI 水体提取 + 河道边界/中心线
│   │   ├── ndvi_fvc.py           # NDVI / FVC 植被覆盖度 + 趋势检验
│   │   ├── river_change.py       # 河道摆动幅度、频率、主槽变化
│   │   ├── vegetation.py         # 植被动态响应分析（缓冲区统计）
│   │   └── regression.py         # 多元回归（气候、土地利用驱动因子）
│   └── visualization/
│       ├── maps.py               # 静态地图生成
│       ├── timeseries_plot.py    # 时序折线图、趋势图、热力图
│       └── report.py             # 自动化 HTML 报告生成（Jinja2）
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_river_channel_analysis.ipynb
│   ├── 04_vegetation_analysis.ipynb
│   └── 05_correlation_analysis.ipynb
└── tests/
    ├── test_stac_client.py
    ├── test_modis.py
    ├── test_climate.py
    ├── test_ndwi.py
    └── test_ndvi.py
```

---

## 二、数据平台选型（完全替代 Google Earth Engine）

| 数据类型 | 来源 | API / 访问方式 | 分辨率 | 是否需账号 | 是否需下载 |
|----------|------|----------------|--------|-----------|-----------|
| **植被指数 NDVI/EVI** | MODIS MOD13Q1（NASA） | Planetary Computer STAC + stackstac 懒加载 | **250 m**，16 天 | ❌ 无需 | ❌ 按需流式 |
| **地表反射率** | MODIS MOD09A1（NASA） | Planetary Computer STAC + stackstac 懒加载 | **500 m**，8 天 | ❌ 无需 | ❌ 按需流式 |
| **水体掩膜** | MODIS MOD44W（NASA） | Planetary Computer STAC + stackstac 懒加载 | **250 m**，年度 | ❌ 无需 | ❌ 按需流式 |
| **水体历史参考** | JRC Global Surface Water（EC） | COG 直连 / Planetary Computer STAC | 30 m | ❌ 无需 | ❌ range-request |
| **气候驱动因子** | Open-Meteo 历史归档（ERA5） | **REST API**（HTTP GET） | ~9 km | ❌ 无需 | ❌ JSON 直返 |
| **高分补充（可选）** | Sentinel-2 L2A | Earth Search STAC | 10 m | ❌ 无需 | ❌ 按需流式 |

### 数据量对比（MODIS vs Landsat）

| 指标 | Landsat（原方案） | MODIS MOD13Q1（新方案） |
|------|-----------------|----------------------|
| 分辨率 | 30 m | 250 m |
| 单景像元数（松辽流域） | ~1.6 × 10⁹ | ~2.3 × 10⁷ |
| 相对数据量 | 1× | **约 1/70** |
| 时序密度 | 16 天（晴天） | 16 天（QC 合成，云影响小） |
| 时间覆盖 | 1995 年起 | **2000 年起**（Terra MODIS） |

### 关键 API 调用示例

```python
# ① MODIS NDVI（Planetary Computer，无需账号，无需下载）
from src.data.modis import MODISLoader
loader = MODISLoader()
ndvi_ds = loader.load_ndvi(year=2020, bbox=[119, 40, 132, 50])

# ② Open-Meteo 气候数据（完全免费 REST，无账号，无 API Key）
from src.data.climate import OpenMeteoClient
client = OpenMeteoClient()
df = client.get_annual_stats(lat=45.0, lon=125.5, start_year=2000, end_year=2023)

# ③ JRC 水体历史（COG 直连，无需下载）
from src.data.jrc_water import JRCWaterLoader
loader = JRCWaterLoader()
occ = loader.load_occurrence(bbox=[119, 40, 132, 50])
```

---

## 三、核心技术路线

```
数据获取（STAC API + REST API）
    │
    ├── MODIS NDVI/EVI（250 m，16 天）via Planetary Computer
    ├── MODIS 地表反射率（500 m，8 天）via Planetary Computer
    ├── MODIS 水体掩膜（250 m，年度）via Planetary Computer
    ├── JRC 水体历史（30 m，COG 直连）
    └── Open-Meteo 气候数据（降水/气温，REST API）
    │
    ▼
预处理
├── QC 掩膜（pixel_reliability / sur_refl_qc500m 位运算）
├── 生长季筛选（5–9 月）
├── 年度中值合成（消除残余噪声）
└── 缺失年份线性插值
    │
    ▼
指数计算
├── NDVI / EVI（直接来自 MOD13Q1）
├── NDWI = (Green - NIR) / (Green + NIR)   → 水体提取
└── FVC  = (NDVI - NDVImin) / (NDVImax - NDVImin)
    │
    ▼
空间分析
├── 水体二值化 → 河道边界（skimage 形态学）
├── 中心线骨架化（medial axis）
├── 河道摆动幅度与频率统计
└── 植被-河道缓冲区叠加分析
    │
    ▼
时序分析
├── 年际 NDVI/FVC 趋势（Sen 斜率 + MK 检验）
├── 年际河道面积、宽度变化
└── 相关性分析（Pearson / Spearman）
    │
    ▼
驱动因子分析（Open-Meteo 数据）
├── 输入：年均降雨量、年均气温、蒸散发（ET₀）
└── 多元线性回归 / 偏相关分析
    │
    ▼
可视化与报告
├── 静态地图（逐年河道 + 植被）
├── 时序折线图 / 相关热力图
└── 自动化 HTML 报告（Jinja2）
```

---

## 四、实施阶段与里程碑

| 阶段 | 时间 | 任务 | 产出 |
|------|------|------|------|
| Phase 0 | 2025-05~06 | 环境搭建、MODIS/Open-Meteo API 验证 | Notebook 演示数据访问 |
| Phase 1 | 2025-07~08 | 预处理流程、MODIS 时序数据集构建 | 2000–2024 年 NDVI 时序图 |
| Phase 2 | 2025-09~10 | 水体提取、河道变迁分析 | 河道中心线迁移图、面积统计表 |
| Phase 3 | 2025-11~12 | 植被响应分析、气候相关性模型 | 植被-河道响应图、回归报告 |
| Phase 4 | 2026-01~02 | 系统开发（后端+前端）、自动报告 | Web 演示系统 |
| Phase 5 | 2026-03~04 | 测试优化、论文撰写、结题 | 论文草稿、系统部署 |

---

## 五、主要依赖库

| 库 | 用途 |
|----|------|
| `pystac-client` | STAC API 搜索 |
| `planetary-computer` | Planetary Computer 资产签名（免费） |
| `stackstac` | STAC Items → xarray（懒加载，无需预下载） |
| `rioxarray` | 栅格 IO、COG range-request |
| `requests` | Open-Meteo REST API |
| `geopandas` | 矢量数据 |
| `scikit-image` | 形态学（骨架化、中心线） |
| `scipy` | 统计检验（MK、相关性） |
| `scikit-learn` | 多元回归 |
| `pymannkendall` | Mann-Kendall 趋势检验 |
| `matplotlib` | 静态地图与图表 |
| `folium` | 交互式 Web 地图 |
| `jinja2` | HTML 报告模板 |
| `dask` | 并行懒加载计算 |
