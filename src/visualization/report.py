"""
自动化 HTML 报告生成模块
=========================
基于 Jinja2 模板自动生成包含图表和统计数据的 HTML 分析报告。

用法示例
--------
>>> from src.visualization.report import ReportGenerator
>>> gen = ReportGenerator(output_dir="outputs/reports")
>>> gen.generate(
...     title="松辽流域河道变迁与植被响应分析报告",
...     sections=[...],
...     figures_dir="outputs/figures",
... )
"""

from __future__ import annotations

import base64
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from jinja2 import Environment, BaseLoader


# ──────────────────────────────────────────
# HTML 报告模板
# ──────────────────────────────────────────
_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }}</title>
  <style>
    body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 40px; color: #333; }
    h1 { color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 8px; }
    h2 { color: #1f618d; margin-top: 32px; }
    h3 { color: #2874a6; }
    table { border-collapse: collapse; width: 100%; margin: 16px 0; }
    th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; }
    th { background: #d6eaf8; font-weight: bold; }
    tr:nth-child(even) { background: #f5f5f5; }
    .figure-block { text-align: center; margin: 20px 0; }
    .figure-block img { max-width: 90%; border: 1px solid #ddd; border-radius: 4px; }
    .figure-caption { font-size: 0.9em; color: #666; margin-top: 6px; }
    .stat-box { background: #eaf4fb; border-left: 4px solid #2980b9;
                padding: 12px 16px; margin: 16px 0; border-radius: 4px; }
    .footer { margin-top: 48px; font-size: 0.85em; color: #aaa; border-top: 1px solid #ddd;
              padding-top: 12px; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <p><strong>生成时间：</strong>{{ generated_at }}&emsp;
     <strong>研究区域：</strong>松辽流域（{{ bbox }}）&emsp;
     <strong>时间范围：</strong>{{ year_range }}</p>

  {% for section in sections %}
  <h2>{{ loop.index }}. {{ section.title }}</h2>

  {% if section.description %}
  <p>{{ section.description }}</p>
  {% endif %}

  {% if section.stat_box %}
  <div class="stat-box">{{ section.stat_box }}</div>
  {% endif %}

  {% if section.table %}
  <table>
    <thead><tr>{% for col in section.table.columns %}<th>{{ col }}</th>{% endfor %}</tr></thead>
    <tbody>
    {% for row in section.table.rows %}
      <tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% for fig in section.figures %}
  <div class="figure-block">
    <img src="{{ fig.path }}" alt="{{ fig.caption }}">
    <p class="figure-caption">图：{{ fig.caption }}</p>
  </div>
  {% endfor %}

  {% endfor %}

  <div class="footer">
    本报告由松辽流域遥感分析系统自动生成 &bull; 数据来源：Microsoft Planetary Computer / Earth Search
  </div>
</body>
</html>
"""


class ReportGenerator:
    """
    HTML 分析报告生成器。

    Parameters
    ----------
    output_dir : str  报告输出目录
    """

    def __init__(self, output_dir: str = "outputs/reports") -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._env = Environment(loader=BaseLoader())
        self._tmpl = self._env.from_string(_REPORT_TEMPLATE)

    def generate(
        self,
        title: str,
        sections: List[Dict[str, Any]],
        bbox: str = "119°E–132°E, 40°N–50°N",
        year_range: str = "1995–2025",
        filename: str = "report.html",
        embed_images: bool = False,
    ) -> str:
        """
        生成 HTML 报告。

        Parameters
        ----------
        title : str  报告标题
        sections : list of dict
            每个 section 是一个字典，包含：
              - title (str)：章节标题
              - description (str, optional)：章节描述
              - stat_box (str, optional)：高亮统计摘要
              - table (dict, optional)：{"columns": [...], "rows": [[...], ...]}
              - figures (list of dict, optional)：[{"path": "...", "caption": "..."}]
        bbox : str  研究区描述
        year_range : str  时间范围描述
        filename : str  输出文件名
        embed_images : bool  是否将图片 base64 嵌入 HTML（便于离线分发）

        Returns
        -------
        str  输出文件完整路径
        """
        if embed_images:
            sections = self._embed_images(sections)

        html = self._tmpl.render(
            title=title,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            bbox=bbox,
            year_range=year_range,
            sections=sections,
        )

        out_path = os.path.join(self.output_dir, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"报告已生成：{out_path}")
        return out_path

    def _embed_images(self, sections: List[Dict]) -> List[Dict]:
        """将 figure.path 替换为 data URI（base64）。"""
        import copy

        sections = copy.deepcopy(sections)
        for section in sections:
            for fig in section.get("figures", []):
                path = fig.get("path", "")
                if os.path.isfile(path):
                    ext = os.path.splitext(path)[1].lstrip(".").lower()
                    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
                    with open(path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    fig["path"] = f"data:{mime};base64,{b64}"
        return sections

    @staticmethod
    def dataframe_to_table(df) -> Dict[str, Any]:
        """
        将 pandas DataFrame 转换为模板所需的 table 字典。

        Parameters
        ----------
        df : pd.DataFrame

        Returns
        -------
        dict  {"columns": [...], "rows": [[...], ...]}
        """
        return {
            "columns": [""] + list(df.columns) if df.index.name else list(df.columns),
            "rows": [
                [str(idx)] + [str(v) for v in row] for idx, row in df.iterrows()
            ],
        }
