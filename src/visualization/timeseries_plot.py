"""
时序图表模块
============
绘制年际变化折线图、趋势图、热力图等。

用法示例
--------
>>> from src.visualization.timeseries_plot import TimeSeriesPlotter
>>> plotter = TimeSeriesPlotter(output_dir="outputs/figures")
>>> plotter.plot_ndvi_trend(ndvi_annual_mean, title="松辽流域 NDVI 年际变化")
"""

from __future__ import annotations

import os
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class TimeSeriesPlotter:
    """
    时序折线图绘制器。

    Parameters
    ----------
    output_dir : str  图像输出目录
    figsize : tuple
    dpi : int
    """

    def __init__(
        self,
        output_dir: str = "outputs/figures",
        figsize=(12, 5),
        dpi: int = 150,
    ) -> None:
        self.output_dir = output_dir
        self.dpi = dpi
        self.figsize = figsize
        os.makedirs(output_dir, exist_ok=True)

    def plot_ndvi_trend(
        self,
        ndvi_series: pd.Series,
        title: str = "松辽流域年均 NDVI 变化（1995–2025）",
        trend_line: bool = True,
        save_name: str = "ndvi_trend.png",
    ) -> plt.Figure:
        """
        绘制 NDVI 年际趋势折线图，可叠加线性趋势线。

        Parameters
        ----------
        ndvi_series : pd.Series  index=year, values=ndvi_mean
        title : str
        trend_line : bool  是否绘制趋势线
        save_name : str

        Returns
        -------
        plt.Figure
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        years = ndvi_series.index.values
        values = ndvi_series.values

        ax.plot(years, values, "o-", color="#2ca02c", linewidth=1.5, markersize=5, label="年均 NDVI")
        ax.fill_between(years, values, alpha=0.15, color="#2ca02c")

        if trend_line:
            valid = ~np.isnan(values)
            if valid.sum() >= 2:
                z = np.polyfit(years[valid], values[valid], 1)
                p = np.poly1d(z)
                ax.plot(years, p(years), "--", color="#d62728", linewidth=1.5,
                        label=f"趋势线 (slope={z[0]:.4f}/yr)")

        ax.set_xlabel("年份", fontsize=11)
        ax.set_ylabel("NDVI", fontsize=11)
        ax.set_title(title, fontsize=13)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        path = os.path.join(self.output_dir, save_name)
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        print(f"已保存：{path}")
        return fig

    def plot_multi_indicator(
        self,
        df: pd.DataFrame,
        title: str = "松辽流域多指标年际变化",
        save_name: str = "multi_indicator.png",
    ) -> plt.Figure:
        """
        绘制多指标对比折线图（双 Y 轴）。

        Parameters
        ----------
        df : pd.DataFrame
            index=year，列为指标名称（如 ndvi_mean, area_km2, rainfall_mm）。
        """
        fig, ax1 = plt.subplots(figsize=self.figsize)

        colors = plt.cm.Set1(np.linspace(0, 0.8, len(df.columns)))
        years = df.index.values

        ax2 = ax1.twinx()
        axes = [ax1, ax2]

        for i, col in enumerate(df.columns):
            ax = axes[i % 2]
            ax.plot(years, df[col].values, "o-", color=colors[i],
                    linewidth=1.5, markersize=4, label=col)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper left")

        ax1.set_xlabel("年份", fontsize=11)
        ax1.grid(True, alpha=0.3)
        fig.suptitle(title, fontsize=13)
        plt.tight_layout()

        path = os.path.join(self.output_dir, save_name)
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        print(f"已保存：{path}")
        return fig

    def plot_correlation_heatmap(
        self,
        corr_matrix: pd.DataFrame,
        title: str = "驱动因子相关矩阵",
        save_name: str = "correlation_heatmap.png",
    ) -> plt.Figure:
        """绘制相关系数热力图。"""
        fig, ax = plt.subplots(figsize=(8, 7))

        cmap = plt.cm.RdBu_r
        im = ax.imshow(corr_matrix.values, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        labels = list(corr_matrix.columns)
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
        ax.set_yticklabels(labels, fontsize=9)

        # 在格子内显示数值
        for i in range(len(labels)):
            for j in range(len(labels)):
                val = corr_matrix.values[i, j]
                color = "white" if abs(val) > 0.7 else "black"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=8, color=color)

        ax.set_title(title, fontsize=13, pad=12)
        plt.tight_layout()

        path = os.path.join(self.output_dir, save_name)
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        print(f"已保存：{path}")
        return fig

    def plot_river_area_change(
        self,
        area_series: pd.Series,
        title: str = "松辽流域河道面积年际变化",
        save_name: str = "river_area_change.png",
    ) -> plt.Figure:
        """绘制河道面积变化柱状 + 折线叠加图。"""
        fig, ax = plt.subplots(figsize=self.figsize)

        years = area_series.index.values
        values = area_series.values
        base = values[0] if len(values) > 0 else 0
        changes = values - base

        colors = ["#d62728" if c < 0 else "#2ca02c" for c in changes]
        ax.bar(years, changes, color=colors, alpha=0.7, label="面积相对变化（km²）")
        ax.axhline(0, color="black", linewidth=0.8)
        ax.plot(years, values - base, "o-", color="#1f77b4", linewidth=1.2,
                markersize=4, label="累积变化趋势")

        ax.set_xlabel("年份", fontsize=11)
        ax.set_ylabel("面积变化（km²）", fontsize=11)
        ax.set_title(title, fontsize=13)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()

        path = os.path.join(self.output_dir, save_name)
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        print(f"已保存：{path}")
        return fig
