# RaceHub 赛事日历

一个聚合 **F1、WEC 赛车** 与 **CS2 电竞** 赛事信息的中文桌面应用：

- 📅 赛事日历（已结束 / 进行中 / 即将开始 + 倒计时）
- 🏁 比赛结果（F1 各站成绩、WEC 各分站最终成绩、CS2 对阵与赛果）
- 🎯 积分排名（F1 车手/车队积分、WEC 四大榜单、CS2 HLTV 世界排名）
- 🗺️ CS2 各局比分（点击比赛后按需从 HLTV 比赛详情页抓取，BO1/BO3/BO5 逐图比分）
- 🪟 大窗口显示详细内容 + 可置顶迷你窗口显示最近关键赛程

三个项目在界面中以独立标签页分开（F1 赛车 / WEC 耐力赛 / CS2 电竞）。

---

## 数据来源

| 项目 | 数据 | 来源 |
| --- | --- | --- |
| F1 | 赛程 / 结果 / 车手·车队积分 | [Ergast API 镜像](https://api.jolpi.ca/ergast/) |
| WEC | 赛程 / 积分 | [FIA WEC 官网](https://www.fiawec.com/) |
| WEC | 分站最终成绩 | [FIA WEC 官方计时系统](https://fiawec.alkamelsystems.com/)（CSV） |
| CS2 | 赛事日历 / 对阵赛果 / 世界排名 / 各局比分 | [HLTV](https://www.hltv.org/) |

所有抓取结果会缓存到本地 `data/cache/`，离线时自动使用缓存或内置示例数据（`data/demo/`），界面会明确标注「实时数据 / 示例数据」。

## 运行环境

- Windows 10/11，Python 3.10+（自带 tkinter 即可，无需额外 GUI 依赖）
- 依赖：`requests`、`beautifulsoup4`（可选：`cloudscraper` 提升 HLTV 抓取成功率）

## 快速开始

```bat
:: 1. 安装依赖（首次）
pip install -r requirements.txt

:: 2. 启动
python main.py
:: 或直接双击
run.bat
```

离线 / 演示模式（不联网，仅使用缓存与示例数据）：

```bat
python main.py --offline
```

## 使用说明

### 主窗口
- 顶部三个标签页分别对应 **F1 赛车 / WEC 耐力赛 / CS2 电竞**。
- 每个项目内分三个子页：**赛程 / 赛果 / 积分**。
  - F1：赛程表点击某站可跳转查看该站结果；积分页可切换车手/车队榜。
  - WEC：赛果页展示官方计时最终成绩（Hypercar 与 LMGT3 同表）；积分页可切换厂商/车手/车队/LMGT3 榜单。
  - CS2：赛果页展示近期对阵（含比分与 BO 信息），点击比赛会按需抓取并展示**各局比分**，可一键打开 HLTV 原页面；积分页为 HLTV 世界排名。
- 右上角「🔄 全部刷新」抓取全部数据；「⚙ 设置」可配置代理、离线模式、缓存时长与自动刷新间隔。

### 迷你窗口（置顶）
- 点击顶栏「🗔 迷你窗」或菜单「视图 → 显示/隐藏迷你窗」。
- 默认置顶显示未来 5 场关键赛事（跨 F1/WEC/CS2，按日期排序，带倒计时）。
- 可拖动、可关闭/重新打开；「📌 置顶」按钮可切换是否始终置顶。

### 关于 HLTV（CS2）
HLTV 有 Cloudflare 防护，且对不同 IP/请求的拦截是**间歇性**的。本应用内置了：

1. 自动重试（最多 4 次，cloudscraper 与普通请求交替）；
2. 配置代理后显著提高成功率（如 Clash/V2Ray 的 `http://127.0.0.1:7890`，在「设置」中填写，或设置环境变量后重启）；
3. 抓取失败 / 返回数据异常时自动保留上一次成功数据，并明确标注状态；
4. 内置示例数据兜底，保证应用始终可用。

> 若 HLTV 在你所在网络完全不可达，CS2 页会显示「示例数据 · 离线」；配置可用代理后点击「全部刷新」即可拉取实时数据。

## 项目结构

```
赛事日历/
├── main.py                  # 启动入口
├── run.bat                  # Windows 一键启动
├── requirements.txt
├── config.json              # 运行配置（代理、离线、TTL…，首次保存后生成）
├── data/
│   ├── cache/               # 抓取结果缓存（JSON）
│   └── demo/                # 内置示例数据（离线兜底）
├── racehub/
│   ├── app.py               # 主应用（窗口、菜单、设置、自动刷新）
│   ├── store.py             # 数据中心：缓存/示例回退/后台刷新
│   ├── fetcher.py           # HTTP 抓取（UA 轮换、代理、cloudscraper）
│   ├── scrapers/
│   │   ├── f1.py            # F1：Ergast 镜像
│   │   ├── wec.py           # WEC：官网 + 官方计时
│   │   └── cs2.py           # CS2：HLTV
│   └── ui/
│       ├── main_window/面板  # 主窗口（base/f1/wec/cs2 面板）
│       ├── mini_window.py   # 置顶迷你窗
│       ├── theme.py         # 深色主题
│       └── widgets.py       # 通用组件
└── scripts/
    ├── gen_demo.py          # 重新生成内置示例数据
    └── test_scrapers.py     # 爬虫冒烟测试
```

## 重新生成示例数据

```bat
python scripts\gen_demo.py
```

## 免责声明

- 数据来源于公开网站，版权归原网站所有；本工具仅供个人学习与信息聚合，请勿用于商业用途。
- 请合理控制抓取频率；HLTV 等网站可能随时调整页面结构，导致部分解析失效，我们会尽量让解析器保持容错。
