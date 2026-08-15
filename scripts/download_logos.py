"""批量下载 CS2 全部缺失队标（真实队标 + 白底 + 本地保存）。

用法（在你网络能访问 HLTV 时运行，一次性补齐所有队标）：
    python scripts/download_logos.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from racehub.config import DATA_DIR
from racehub.ui.team_logos import _safe, collect_team_logos, logo_manager


def main():
    teams = collect_team_logos()
    logos_dir = DATA_DIR / "logos"
    logos_dir.mkdir(parents=True, exist_ok=True)
    missing = {
        n: u for n, u in teams.items()
        if u and not (logos_dir / f"{_safe(n)}.png").exists()
    }
    print(f"队伍总数: {len(teams)}")
    print(f"本地已有: {len(teams) - len(missing)}")
    print(f"待下载: {len(missing)}")
    if not missing:
        print("没有缺失队标，完成。")
        return

    logo_manager.reset_retry()
    ok_cnt = 0
    t0 = time.time()

    def progress(name, ok, done, total):
        nonlocal ok_cnt
        if ok:
            ok_cnt += 1
        pct = done * 100 // total
        print(f"[{done:>3}/{total}] {pct:>3}%  {name}: {'OK ' if ok else 'FAIL'}")

    logo_manager.download_all_sync(missing, progress=progress)
    print("-" * 50)
    print(f"完成：成功 {ok_cnt} / {len(missing)}，用时 {time.time()-t0:.0f} 秒")
    print("失败的队伍 24 小时内会自动跳过；之后可再次运行本脚本重试。")
    print("提示：应用内 帮助 → 🖼 下载全部 CS2 队标 也可直接补全。")


if __name__ == "__main__":
    main()
