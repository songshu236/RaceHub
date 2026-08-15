"""RaceHub 启动入口：python main.py [--offline]"""
from __future__ import annotations

import argparse


def enable_dpi_awareness():
    """让 Tk 在 Windows 高 DPI 缩放下正确渲染（部分系统默认会导致窗口内容异常）。"""
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def main():
    enable_dpi_awareness()
    parser = argparse.ArgumentParser(description="RaceHub 赛事日历聚合应用")
    parser.add_argument("--offline", action="store_true", help="离线模式（不联网，使用缓存/示例数据）")
    parser.add_argument("--selftest", action="store_true", help="仅打印数据加载诊断信息后退出（不打开窗口）")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    from racehub.app import RaceHubApp

    app = RaceHubApp(offline=args.offline)
    app.mainloop()


def run_selftest():
    """无界面自检：验证数据能否加载、各项目条数，供排查“空窗口”问题。"""
    import sys
    from racehub.config import load_config
    from racehub.store import SERIES_LIST, DataStore

    print("RaceHub 自检")
    print("=" * 50)
    print("Python:", sys.version.split()[0])
    try:
        import tkinter
        print("tkinter:", tkinter.TkVersion)
    except Exception as e:
        print("tkinter: 不可用 ->", e)
        return

    cfg = dict(load_config())
    store = DataStore(cfg)
    total = 0
    for series in SERIES_LIST:
        for kind in ("calendar", "results", "standings", "matches", "ranking"):
            p = store.get(series, kind)
            if p is None:
                continue
            n = len(p) if isinstance(p, list) else (len(p.get("rows", [])) or len(p.get("tables", [])))
            m = store.meta(series, kind)
            tag = "示例" if m.get("using_demo") else ("缓存" if m.get("fetched_at") else "无")
            print(f"  {series:>3}/{kind:<10}: {n:>4} 条  [{tag}]  {m.get('source','')}")
            total += n
    print("-" * 50)
    print("数据总条数:", total)
    if total == 0:
        print("警告：没有加载到任何数据！请运行: python scripts\\gen_demo.py 重新生成示例数据。")
    else:
        print("数据加载正常：应用窗口应能显示内容。")
        print("如果窗口仍然空白，请打开应用后 帮助→诊断信息，并把内容发给我们。")


if __name__ == "__main__":
    main()
