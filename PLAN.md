# 松辽流域河道变迁与植被响应分析系统 — 工程计划书

> **项目名称**：从遥感视角揭示过去三十年松辽流域河道变迁及其对周围植被的影响  
> **数据平台**：Microsoft Planetary Computer STAC API + Earth Search（替代 Google Earth Engine）  
> **核心优势**：免费直连、无需预下载、支持 Landsat 5/7/8/9 及 Sentinel-2 全时序数据

---

## 一、整体架构

```
songliao-analysis/
├── PLAN.md                    # 本计划书
├── README.md                  # 项目说明
├── requirements.txt           # Python 依赖
├── config.py                  # 全局配置（研究区、时间范围、参数）
├── src/
│   ├── data/
│   │   ├── stac_client.py     # STAC API 统一客户端（Planetary Computer / Earth Search）
│   │   ├── landsat.py         # Landsat 5/7/8/9 数据获取与预处理
│   │   └── sentinel2.py       # Sentinel-2 数据获取与预处理
│   ├── processing/
│   │   ├── preprocessing.py   # 云掩膜、大气校正、辐射归一化
│   │   ├── fusion.py          # 多传感器影像融合（30 m 统一分辨率）
│   │   └── timeseries.py      # 长时序数据集构建（1995–2025）
│   ├── analysis/
│   │   ├── ndwi.py            # NDWI 水体提取 + 河道边界/中心线
│   │   ├── ndvi_fvc.py        # NDVI / FVC 植被覆盖度计算
│   │   ├── river_change.py    # 河道摆动幅度、频率、主槽变化检测
│   │   ├── vegetation.py      # 植被动态响应分析（空间匹配）
│   │   └── regression.py      # 多元回归（降雨、土地利用等驱动因子）
│   └── visualization/
│       ├── maps.py            # 静态地图生成（matplotlib / cartopy）
│       ├── timeseries_plot.py # 时序折线图、趋势图
│       └── report.py          # 自动化 HTML/PDF 报告生成
├── notebooks/
│   ├── 01_data_exploration.ipynb       # 数据探索与可视化
│   ├── 02_preprocessing.ipynb         # 预处理流程演示
│   ├── 03_river_channel_analysis.ipynb # 河道变迁分析
│   ├── 04_vegetation_analysis.ipynb   # 植被覆盖度分析
│   └── 05_correlation_analysis.ipynb  # 河道-植被相关性与驱动因子
└── tests/
    ├── test_stac_client.py
    ├── test_ndwi.py
    └── test_ndvi.py
```

---

## 二、数据平台选型（替代 Google Earth Engine）

| 方案 | 平台 | 免费 | 无需预下载 | Landsat | Sentinel-2 | 说明 |
|------|------|------|------------|---------|------------|------|
| **主选** | Microsoft Planetary Computer | ✅ | ✅ | ✅ 5/7/8/9 | ✅ L2A | STAC API，Python SDK，计算量大时可申请免费 Hub |
| **备选** | Earth Search (AWS Element84) | ✅ | ✅ | ✅ C2 L2 | ✅ L2A | 公开 STAC，数据存 S3，无账号限制 |
| **补充** | NASA Earthdata (earthaccess) | ✅ | ✅ | ✅ | —— | 免费账号，HLS 融合产品 |

**访问方式（Python）**：
```python
import pystac_client
import planetary_computer

# Planetary Computer（无需账号，公开数据集直接访问）
catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)

# Earth Search（无需账号）
catalog = pystac_client.Client.open(
    "https://earth-search.aws.element84.com/v1"
)
```

---

## 三、核心技术路线

```
数据获取（STAC API）
    │
    ▼
预处理
├── 云掩膜（QA_PIXEL / SCL）
├── 大气校正（使用表面反射率产品，免二次校正）
├── 分辨率统一（30 m，stackstac/rioxarray 重采样）
└── 辐射归一化（6S 模型 / 直方图匹配）
    │
    ▼
指数计算
├── NDWI = (Green - NIR) / (Green + NIR)  → 水体提取
├── NDVI = (NIR - Red) / (NIR + Red)      → 植被活力
└── FVC  = (NDVI - NDVImin) / (NDVImax - NDVImin)  → 植被覆盖度
    │
    ▼
空间分析
├── 水体二值化 → 河道边界提取（skimage 形态学操作）
├── 中心线提取（medial axis / 骨架化）
├── 河道摆动幅度与频率统计
└── 植被-河道空间叠加分析（缓冲区统计）
    │
    ▼
时序分析
├── 年际 NDVI/FVC 趋势（Sen 斜率 + MK 检验）
├── 年际河道面积、宽度变化
└── 相关性分析（Pearson / Spearman）
    │
    ▼
驱动因子分析
├── 输入：降雨量、气温、土地利用变化、水利工程
└── 多元回归 / GWR 地理加权回归
    │
    ▼
可视化与报告
├── 静态地图（每年河道 + 植被覆盖）
├── 时序折线图 / 热力图
└── 自动化 HTML 报告（Jinja2 模板）
```

---

## 四、实施阶段与里程碑

| 阶段 | 时间 | 任务 | 产出 |
|------|------|------|------|
| Phase 0 | 2025-05~06 | 环境搭建、数据探索、API 验证 | Jupyter Notebook 演示数据访问 |
| Phase 1 | 2025-07~08 | 预处理流程、时序数据集构建 | 1995–2025 年 NDVI 时序图 |
| Phase 2 | 2025-09~10 | 河道提取与变迁分析 | 河道中心线迁移图、面积统计表 |
| Phase 3 | 2025-11~12 | 植被响应分析、相关性模型 | 植被-河道响应图、回归报告 |
| Phase 4 | 2026-01~02 | 系统开发（后端+前端）、自动报告 | Web 演示系统 |
| Phase 5 | 2026-03~04 | 测试优化、论文撰写、结题 | 论文草稿、系统部署 |

---

## 五、主要依赖库

| 库 | 用途 |
|----|------|
| `pystac-client` | STAC API 搜索 |
| `planetary-computer` | Planetary Computer 签名 |
| `stackstac` | STAC Items → xarray DataArray（懒加载，无需预下载） |
| `rioxarray` | 栅格 IO、重投影、裁剪 |
| `geopandas` | 矢量数据（流域边界、河道多边形） |
| `scikit-image` | 形态学操作（骨架化、中心线提取） |
| `scipy` | 统计检验（MK 趋势检验、相关性） |
| `scikit-learn` | 多元回归分析 |
| `pymannkendall` | Mann-Kendall 趋势检验 |
| `matplotlib` / `cartopy` | 静态地图与图表 |
| `folium` | 交互式 Web 地图 |
| `jinja2` | 自动化 HTML 报告模板 |
| `dask` | 并行计算（大影像懒加载） |
