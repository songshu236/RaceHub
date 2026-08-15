"""队伍队标：彩色圆角徽章 + 队名缩写。

用 PIL 生成 28x28 圆角徽章（白色缩写文字 + 队色背景），
PIL 不可用时回退为纯色方块。生成的 PhotoImage 会缓存，避免重复创建。
"""
from __future__ import annotations

import hashlib
import tkinter as tk

# 常见队伍主色（找不到时按名字哈希取色）
TEAM_COLORS = {
    # --- F1 车队 ---
    "Mercedes": "#00D2BE", "Ferrari": "#E8002D", "Red Bull": "#3671C6",
    "McLaren": "#FF8000", "Aston Martin": "#229971", "Alpine": "#FF87BC",
    "Williams": "#64C4FF", "RB": "#6692FF", "Racing Bulls": "#6692FF",
    "Sauber": "#52E252", "Kick Sauber": "#52E252", "Haas": "#B6BABD",
    "Audi": "#C92F4A", "Cadillac": "#3F48CC",
    # --- WEC 车队 ---
    "Toyota Racing": "#E60012", "Toyota": "#E60012",
    "Ferrari AF Corse": "#FF2800", "AF Corse": "#FF2800",
    "BMW M Team WRT": "#0066B1", "Team WRT": "#0066B1",
    "Cadillac Hertz Team Jota": "#1B1B1B", "Cadillac Racing": "#1B1B1B",
    "Peugeot Totalenergies": "#004B93", "Peugeot": "#004B93",
    "Alpine Endurance Team": "#0078C8",
    "Aston Martin Thor Team": "#00665E", "Aston Martin": "#00665E",
    "Genesis Magma Racing": "#5B0F00",
    "Porsche": "#D5001C", "Manthey": "#D5001C",
    "The Bend Manthey": "#D5001C", "Manthey DK Engineering": "#D5001C",
    "Proton Competition": "#004A9F", "Iron Lynx": "#1A1A1A",
    "Akkodis ASP Team": "#005EB8", "Lexus": "#1A1A1A",
    "TF Sport": "#E31837", "Corvette": "#F5B301",
    "Vista AF Corse": "#FF2800", "Heart of Racing Team": "#00665E",
    "Garage 59": "#FFB81C", "Racing Team Turkey by TF": "#E31837",
    # --- CS2 战队 ---
    "Vitality": "#FFD700", "FaZe": "#E31C23", "NAVI": "#F9E300",
    "Spirit": "#3BC9DB", "MOUZ": "#FFC900", "G2": "#F7F7F7",
    "Liquid": "#00A9E0", "Falcons": "#1E1E1E", "Virtus.pro": "#E8E8E8",
    "Eternal Fire": "#ED1C24", "FURIA": "#FF5600", "MongolZ": "#00A3FF",
    "The MongolZ": "#00A3FF", "Astralis": "#D40000", "3DMAX": "#6A0DAD",
    "Heroic": "#00B2FF", "paiN": "#F7941D", "Complexity": "#9E1F63",
    "BIG": "#2A2A2A", "Imperial": "#1C5FA8", "ENCE": "#0A0A0A",
    "BetBoom": "#E5E5E5", "9 Pandas": "#F5A623", "Sashi": "#7C3AED",
    "GamerLegion": "#13C2C2", "Rare Atom": "#B71C1C", "Lynn Vision": "#00897B",
    "TYLOO": "#E60012", "JiJieHao": "#FF7043", "The Huns": "#B8860B",
    "Wildcard": "#FF8C00", "paiN Gaming": "#F7941D", "100 Thieves": "#E31C23",
    "PARIVISION": "#FF69B4", "K27": "#2F4F4F", "MIBR": "#F2A900",
    "B8": "#FFD500", "FUT": "#E4002B", "Rooster": "#FF6F00",
    "Mindfreak": "#5C6BC0", "Abyssal": "#1565C0", "Ground Zero": "#43A047",
    "Isurus": "#C62828", "Gremio": "#006837", "BetBoom Team": "#E5E5E5",
    "SAW": "#003087", "SAW Youngsters": "#003087", "ex-RUSTEC": "#37474F",
}

_PALETTE = [
    "#E53E3E", "#DD6B20", "#D69E2E", "#38A169", "#319795",
    "#3182CE", "#5A67D8", "#805AD5", "#D53F8C", "#718096",
]

_cache: dict[tuple, tk.PhotoImage] = {}
_size = 30
_font_size = 10
_has_pil = None


def _pil_available() -> bool:
    global _has_pil
    if _has_pil is None:
        try:
            from PIL import Image, ImageDraw, ImageFont  # type: ignore
            _has_pil = True
        except Exception:
            _has_pil = False
    return _has_pil


def team_initials(name: str) -> str:
    parts = [p for p in (name or "").replace("'", " ").replace("-", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) >= 3:
        return (parts[0][0] + parts[1][0] + parts[2][0]).upper()
    if len(parts) == 2:
        return (parts[0][0] + parts[1][0]).upper()
    w = parts[0]
    return (w[:3]).upper()


def team_color(name: str) -> str:
    key = name.strip().lower()
    if key in {k.lower(): v for k, v in TEAM_COLORS.items()}:
        for k, v in TEAM_COLORS.items():
            if k.lower() == key:
                return v
    h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:6], 16)
    return _PALETTE[h % len(_PALETTE)]


def _color_luminance(hexcolor: str) -> float:
    c = hexcolor.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def get_badge(name: str, size: int = 36) -> tk.PhotoImage | None:
    """返回队伍徽章 PhotoImage（缓存）。需要 Tk 根已创建。"""
    if not name:
        return None
    key = (name.strip(), size)
    if key in _cache:
        return _cache[key]
    color = team_color(name)
    initials = team_initials(name)
    text_color = "#ffffff" if _color_luminance(color) < 150 else "#1c2733"

    photo = None
    if _pil_available():
        try:
            from PIL import Image, ImageDraw, ImageFont  # type: ignore
            # 用面板底色做背景（RGB 无透明通道，避免某些 Tk 版本透明渲染异常）
            from . import theme as _theme
            bg = getattr(_theme, "PANEL", "#151d27")
            img = Image.new("RGB", (size, size), bg)
            d = ImageDraw.Draw(img)
            r = max(4, size // 6)
            d.rounded_rectangle((1, 1, size - 2, size - 2), radius=r, fill=color,
                                outline="#3a4657", width=1)
            fs = max(9, size // 3)
            try:
                font = ImageFont.truetype("msyh.ttc", fs)
            except Exception:
                try:
                    font = ImageFont.truetype("arial.ttf", fs)
                except Exception:
                    font = ImageFont.load_default()
            tw = d.textlength(initials, font=font)
            d.text(((size - tw) / 2, (size - fs) / 2 - 1), initials, font=font, fill=text_color)
            from PIL import ImageTk  # type: ignore
            photo = ImageTk.PhotoImage(img)
        except Exception:
            photo = None
    if photo is None:
        # 回退：纯色方块
        photo = tk.PhotoImage(width=size, height=size)
        photo.put(color)
    _cache[key] = photo
    return photo
