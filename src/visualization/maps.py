"""
静态地图生成模块
================
使用 matplotlib + cartopy 生成出版级静态地图：
  - 水体分布图（逐年）
  - 植被覆盖度专题图
  - 河道变迁对比图

用法示例
--------
>>> from src.visualization.maps import MapPlotter
>>> plotter = MapPlotter(output_dir="outputs/figures")
>>> plotter.plot_water_body(water_mask, year=2020)
>>> plotter.plot_ndvi(ndvi_da, year=2020)
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # 非交互后端，适合服务器
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import xarray as xr


class MapPlotter:
    """
    遥感专题地图绘制器。

    Parameters
    ----------
    output_dir : str  图像输出目录
    figsize : tuple  图像尺寸（英寸）
    dpi : int  分辨率
    """

    def __init__(
        self,
        output_dir: str = "outputs/figures",
        figsize: Tuple[int, int] = (10, 8),
        dpi: int = 200,
    ) -> None:
        self.output_dir = output_dir
        self.figsize = figsize
        self.dpi = dpi
        os.makedirs(output_dir, exist_ok=True)

    def plot_water_body(
        self,
        water_mask: xr.DataArray,
        year: int,
        title: Optional[str] = None,
        save: bool = True,
    ) -> plt.Figure:
        """绘制水体分布图。"""
        fig, ax = plt.subplots(figsize=self.figsize)

        water_np = water_mask.values.astype(float)
        water_np[water_np == 0] = np.nan

        # 坐标轴（假设 x/y 为像元坐标）
        im = ax.imshow(
            water_np,
            cmap="Blues",
            vmin=0,
            vmax=1,
            aspect="equal",
            interpolation="nearest",
        )
        plt.colorbar(im, ax=ax, label="水体（1=水体）", fraction=0.03)
        title = title or f"松辽流域水体分布 — {year} 年"
        ax.set_title(title, fontsize=13, fontproperties=_get_font())
        ax.set_xlabel("像元列", fontproperties=_get_font())
        ax.set_ylabel("像元行", fontproperties=_get_font())

        if save:
            path = os.path.join(self.output_dir, f"water_body_{year}.png")
            fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
            print(f"已保存：{path}")

        return fig

    def plot_ndvi(
        self,
        ndvi: xr.DataArray,
        year: int,
        title: Optional[str] = None,
        save: bool = True,
    ) -> plt.Figure:
        """绘制 NDVI 植被指数专题图。"""
        fig, ax = plt.subplots(figsize=self.figsize)

        im = ax.imshow(
            ndvi.values,
            cmap="RdYlGn",
            vmin=-0.2,
            vmax=0.9,
            aspect="equal",
            interpolation="nearest",
        )
        plt.colorbar(im, ax=ax, label="NDVI", fraction=0.03)
        title = title or f"松辽流域 NDVI — {year} 年"
        ax.set_title(title, fontsize=13, fontproperties=_get_font())

        if save:
            path = os.path.join(self.output_dir, f"ndvi_{year}.png")
            fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
            print(f"已保存：{path}")

        return fig

    def plot_change_comparison(
        self,
        mask_before: xr.DataArray,
        mask_after: xr.DataArray,
        year_before: int,
        year_after: int,
        save: bool = True,
    ) -> plt.Figure:
        """绘制河道变迁前后对比图。"""
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))

        change = mask_after.values.astype(int) - mask_before.values.astype(int)
        cmap_change = mcolors.ListedColormap(["#d62728", "#aec7e8", "#2ca02c"])
        bounds = [-1.5, -0.5, 0.5, 1.5]
        norm = mcolors.BoundaryNorm(bounds, cmap_change.N)

        for ax, data, title in zip(
            axes,
            [mask_before.values, mask_after.values, change],
            [f"{year_before} 年水体", f"{year_after} 年水体", "变化（绿=新增，红=消失）"],
        ):
            ax.imshow(data, cmap="Blues" if "变化" not in title else cmap_change,
                      norm=norm if "变化" in title else None,
                      aspect="equal", interpolation="nearest")
            ax.set_title(title, fontsize=11, fontproperties=_get_font())
            ax.axis("off")

        plt.tight_layout()

        if save:
            path = os.path.join(self.output_dir, f"change_{year_before}_{year_after}.png")
            fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
            print(f"已保存：{path}")

        return fig

    def plot_fvc(
        self,
        fvc: xr.DataArray,
        year: int,
        title: Optional[str] = None,
        save: bool = True,
    ) -> plt.Figure:
        """绘制植被覆盖度（FVC）专题图。"""
        fig, ax = plt.subplots(figsize=self.figsize)

        im = ax.imshow(
            fvc.values,
            cmap="YlGn",
            vmin=0,
            vmax=1,
            aspect="equal",
            interpolation="nearest",
        )
        plt.colorbar(im, ax=ax, label="FVC [0,1]", fraction=0.03)
        title = title or f"松辽流域植被覆盖度 — {year} 年"
        ax.set_title(title, fontsize=13, fontproperties=_get_font())

        if save:
            path = os.path.join(self.output_dir, f"fvc_{year}.png")
            fig.savefig(path, dpi=self.dpi, bbox_inches="tight")

        return fig


def _get_font():
    """获取支持中文的字体属性（若系统无中文字体则回退默认）。"""
    import matplotlib.font_manager as fm

    # 尝试常见中文字体
    for font_name in ["SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "PingFang SC"]:
        try:
            prop = fm.FontProperties(family=font_name)
            return prop
        except Exception:
            continue
    return fm.FontProperties()
