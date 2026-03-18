# 松辽流域河道变迁与植被响应分析系统

> 从遥感视角揭示过去三十年松辽流域河道变迁及其对周围植被的影响

## 项目简介

本项目完全替代 Google Earth Engine（GEE），改用以下**免费开源、无需账号、无需预下载**的数据 API：

| 数据类型 | 来源 | 方式 | 分辨率 |
|----------|------|------|--------|
| NDVI / EVI | MODIS MOD13Q1（NASA） | Planetary Computer STAC，stackstac 懒加载 | **250 m**，16 天 |
| 地表反射率 | MODIS MOD09A1（NASA） | Planetary Computer STAC，stackstac 懒加载 | **500 m**，8 天 |
| 水体掩膜 | MODIS MOD44W（NASA） | Planetary Computer STAC，stackstac 懒加载 | **250 m**，年度 |
| 水体历史 | JRC Global Surface Water（EC） | COG 直连（range-request，无需下载） | 30 m |
| 气候驱动因子 | Open-Meteo 历史归档（ERA5） | **REST API**（HTTP GET，无需账号） | ~9 km 格点 |

## 核心特性

- **零账号门槛**：无需 Google、无需 NASA Earthdata 账号
- **无需预下载**：STAC + stackstac 懒加载，COG range-request 按需读取
- **轻量数据**：MODIS 250/500 m 比 Landsat 30 m 数据量小约 70 倍
- **气候数据直取**：Open-Meteo 免费 REST API，一行代码获取 1940–今 的降水/气温
- **全流程自动化**：数据获取 → 预处理 → 指数计算 → 变化检测 → 可视化报告

## 快速开始

```bash
# 1. 克隆项目
git clone <repo_url>
cd songliao-analysis

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行数据探索 Notebook
jupyter notebook notebooks/01_data_exploration.ipynb
```

### 5 分钟体验

```python
# 获取 MODIS NDVI（无账号，无下载）
from src.data.modis import MODISLoader
ndvi = MODISLoader().load_ndvi(year=2020, bbox=[119, 40, 132, 50])
print(ndvi)

# 获取松辽流域气候数据（Open-Meteo，纯 REST，无账号）
from src.data.climate import OpenMeteoClient
df = OpenMeteoClient().get_annual_stats(lat=45.0, lon=125.5, start_year=2000, end_year=2023)
print(df[["precipitation_sum", "temperature_2m_mean"]].head())
```

## 项目结构

```
├── PLAN.md              # 详细工程计划书
├── config.py            # 全局配置
├── requirements.txt     # 依赖
├── src/
│   ├── data/
│   │   ├── modis.py       ← 主力数据（MODIS，懒加载）
│   │   ├── climate.py     ← Open-Meteo 气候 API
│   │   ├── jrc_water.py   ← JRC 水体历史
│   │   ├── stac_client.py ← STAC 通用客户端
│   │   ├── landsat.py     ← 可选（Landsat，备用）
│   │   └── sentinel2.py   ← 可选（Sentinel-2，高分补充）
│   ├── processing/      # 预处理、融合、时序构建
│   ├── analysis/        # NDWI/NDVI/FVC、河道变化、回归
│   └── visualization/   # 地图、图表、HTML 报告
├── notebooks/           # Jupyter Notebook 演示
└── tests/               # 单元测试
```

## 详细计划

参见 [PLAN.md](PLAN.md)