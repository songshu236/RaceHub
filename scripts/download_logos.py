"""批量下载 CS2 全部缺失队标与赛事图标（真实素材 + 白底 + 本地保存）。

用法（在你网络能访问 HLTV 时运行，一次性补齐所有队标/赛事图标）：
    python scripts/download_logos.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from racehub.config import DATA_DIR
from racehub.ui.team_logos import _file_for, collect_event_logos, collect_team_logos, logo_manager


def _download(label, items, kind):
    if not items:
        print(f"{label}: 没有需要下载的条目。")
        return
    missing = {n: u for n, u in items.items() if u and not _file_for(kind, n).exists()}
    print(f"{label}: 总数 {len(items)}，本地已有 {len(items) - len(missing)}，待下载 {len(missing)}")
    if not missing:
        print(f"{label}: 没有缺失素材，完成。")
        return
    ok_cnt = 0
    t0 = time.time()

    def progress(name, ok, done, total):
        nonlocal ok_cnt
        if ok:
            ok_cnt += 1
        pct = done * 100 // total
        print(f"[{done:>3}/{total}] {pct:>3}%  {name}: {'OK ' if ok else 'FAIL'}")

    logo_manager.download_all_sync(missing, progress=progress, kind=kind)
    print(f"{label}: 成功 {ok_cnt} / {len(missing)}，用时 {time.time()-t0:.0f} 秒")


def main():
    logos_dir = DATA_DIR / "logos"
    logos_dir.mkdir(parents=True, exist_ok=True)
    (logos_dir / "events").mkdir(parents=True, exist_ok=True)
    logo_manager.reset_retry()
    _download("队伍队标", collect_team_logos(), "team")
    _download("赛事图标", collect_event_logos(), "event")
    print("-" * 50)
    print("失败的条目 24 小时内会自动跳过；之后可再次运行本脚本重试。")
    print("提示：应用内 帮助 → 🖼 下载全部 CS2 队标与赛事图标 也可直接补全。")


if __name__ == "__main__":
    main()
