"""HTTP 抓取器：UA 轮换、代理、cloudscraper 可选用作 Cloudflare 绕过。"""
from __future__ import annotations

import random

import requests

from .config import load_config

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

_cloudscraper = None


def _get_cloudscraper():
    global _cloudscraper
    if _cloudscraper is None:
        try:
            import cloudscraper  # type: ignore

            _cloudscraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True}
            )
        except Exception:
            _cloudscraper = False
    return _cloudscraper or None


def get_session():
    cfg = load_config()
    s = requests.Session()
    proxy = (cfg.get("proxy") or "").strip()
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    return s


def fetch_text(url: str, timeout: int = 20, headers: dict | None = None, use_cloudscraper: bool = False):
    """返回 (text, status_code)。失败抛异常。"""
    cfg = load_config()
    h = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        h.update(headers)
    proxy = (cfg.get("proxy") or "").strip()

    if use_cloudscraper:
        cs = _get_cloudscraper()
        if cs:
            try:
                r = cs.get(url, timeout=timeout, headers=h)
                return r.text, r.status_code
            except Exception:
                pass  # fall through to plain requests

    s = get_session()
    r = s.get(url, timeout=timeout, headers=h)
    r.raise_for_status()
    return r.text, r.status_code


def fetch_bytes(url: str, timeout: int = 20, use_cloudscraper: bool = False):
    """抓取二进制内容（图片等）。use_cloudscraper 尝试绕过 Cloudflare。"""
    if use_cloudscraper:
        cs = _get_cloudscraper()
        if cs:
            try:
                r = cs.get(url, timeout=timeout)
                if r.status_code == 200 and len(r.content) > 100:
                    return r.content
            except Exception:
                pass
    s = get_session()
    r = s.get(url, timeout=timeout, headers={"User-Agent": random.choice(USER_AGENTS)})
    r.raise_for_status()
    return r.content
