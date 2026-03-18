# 松辽流域河道变迁与植被响应分析系统

> 从遥感视角揭示过去三十年松辽流域河道变迁及其对周围植被的影响

## 项目简介

本项目基于 **Microsoft Planetary Computer** 与 **Earth Search** 免费 STAC API（替代 Google Earth Engine），
利用 Landsat TM/OLI（1995–2025）及 Sentinel-2 多源遥感数据，系统分析松辽流域（松花江 + 辽河）过去三十年
河道形态演变对区域植被覆盖格局的影响机制。

## 核心特性

- **免费直连**：基于公开 STAC API，无需 Google 账号，无需预下载影像
- **懒加载**：通过 `stackstac` 实现按需计算，内存友好
- **全流程自动化**：从数据获取、预处理、指数计算到可视化报告一键运行
- **替代 GEE**：完全基于 Python 开源生态，可本地或云端部署

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

## 项目结构

```
├── PLAN.md              # 详细工程计划书
├── config.py            # 全局配置
├── requirements.txt     # 依赖
├── src/
│   ├── data/            # 数据获取模块（STAC API）
│   ├── processing/      # 预处理模块
│   ├── analysis/        # 分析模块
│   └── visualization/   # 可视化模块
├── notebooks/           # Jupyter Notebook 演示
└── tests/               # 单元测试
```

## 数据来源

| 数据集 | 平台 | Collection ID |
|--------|------|---------------|
| Landsat Collection 2 Level-2 | Planetary Computer | `landsat-c2-l2` |
| Sentinel-2 L2A | Planetary Computer | `sentinel-2-l2a` |
| Landsat C2 L2 | Earth Search | `landsat-c2-l2` |
| Sentinel-2 L2A | Earth Search | `sentinel-2-l2a` |

## 详细计划

参见 [PLAN.md](PLAN.md)