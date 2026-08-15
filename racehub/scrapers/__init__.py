"""数据源爬虫。"""
from .f1 import F1Scraper
from .wec import WECScraper
from .cs2 import CS2Scraper

__all__ = ["F1Scraper", "WECScraper", "CS2Scraper"]
