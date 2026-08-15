"""爬虫基类与公共异常。"""
from __future__ import annotations


class SourceError(Exception):
    """数据源抓取失败。"""


class Scraper:
    series = "base"
    source_label = ""

    def __init__(self):
        self.source_label = self.source_label or self.series
