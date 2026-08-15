"""RaceHub 启动入口：python main.py [--offline]"""
from __future__ import annotations

import argparse


def main():
    parser = argparse.ArgumentParser(description="RaceHub 赛事日历聚合应用")
    parser.add_argument("--offline", action="store_true", help="离线模式（不联网，使用缓存/示例数据）")
    args = parser.parse_args()
    from racehub.app import RaceHubApp

    app = RaceHubApp(offline=args.offline)
    app.mainloop()


if __name__ == "__main__":
    main()
