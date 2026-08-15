"""应用内界面截图诊断：优先 PIL 抓取真实屏幕，失败时回退 ctypes PrintWindow。"""
from __future__ import annotations

import ctypes
import struct
from datetime import datetime
from pathlib import Path
from tkinter import messagebox


def _window_rect(app):
    """返回主窗口在屏幕上的 (left, top, right, bottom)。"""
    try:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(app.winfo_id(), ctypes.byref(rect))
        if rect.right > rect.left and rect.bottom > rect.top:
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        pass
    x = app.winfo_rootx()
    y = app.winfo_rooty()
    return x, y, x + app.winfo_width(), y + app.winfo_height()


def _capture_pil(bbox):
    from PIL import ImageGrab  # type: ignore
    img = ImageGrab.grab(bbox=bbox)
    return img


def _capture_printwindow(hwnd, w, h):
    """ctypes + GDI PrintWindow 抓取窗口为 BMP 字节。"""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    hdc_win = user32.GetWindowDC(hwnd)
    if not hdc_win:
        raise RuntimeError("GetWindowDC failed")
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    bmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
    old = gdi32.SelectObject(hdc_mem, bmp)

    ok = user32.PrintWindow(hwnd, hdc_mem, 2)  # PW_RENDERFULLCONTENT
    if not ok:
        ok = user32.PrintWindow(hwnd, hdc_mem, 0)

    # 读取像素
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h  # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0  # BI_RGB

    stride = ((w * 4 + 3) // 4) * 4
    buf = ctypes.create_string_buffer(h * stride)
    got = gdi32.GetDIBits(hdc_mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    if got == 0:
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_win)
        raise RuntimeError("GetDIBits failed")

    # 组装 BMP 文件
    row_size = stride
    pixel_data = bytes(buf.raw[: h * stride])
    file_size = 14 + 40 + h * stride
    header = b"BM" + struct.pack("<IHHI", file_size, 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 32, 0, h * stride, 0, 0, 0, 0)
    gdi32.SelectObject(hdc_mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_win)
    return header + info + pixel_data


def save_screenshot(app, out_dir: Path) -> Path:
    """抓取主窗口画面保存为 PNG（PIL 不可用时保存为 BMP），返回文件路径。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    left, top, right, bottom = _window_rect(app)
    w, h = right - left, bottom - top

    png_path = out_dir / f"界面截图_{stamp}.png"
    try:
        img = _capture_pil((left, top, right, bottom))
        img.save(png_path)
        return png_path
    except Exception:
        pass

    bmp_path = out_dir / f"界面截图_{stamp}.bmp"
    try:
        data = _capture_printwindow(app.winfo_id(), w, h)
        bmp_path.write_bytes(data)
        return bmp_path
    except Exception:
        messagebox.showerror("截图失败", "无法生成界面截图，请改用 Windows 自带截图 (Win+Shift+S)")
        raise
