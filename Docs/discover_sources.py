#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
discover_sources.py
===================
薩提爾活動 — 來源網站探索腳本（每日工作的第一步）

職責（單一）：
    維護「全台薩提爾活動相關網站」的清單，輸出 Satir_list.md。
    本腳本「不」抓取活動內容；抓活動是各網站專屬爬蟲的工作。

每日工作流：
    1. python discover_sources.py   ← 本腳本，重建 Satir_list.md
    2. 依 Satir_list.md 逐一執行各網站爬蟲，更新 events.json
    3. 前端（GitHub Pages）讀 events.json 呈現

設計理念：
    - SEED_SOURCES：人工維護的「已知來源」名冊（核心事實來源）。
      新增一個機構，就在這裡加一筆；之後再替它寫專屬爬蟲。
    - 每次執行會對每個來源做「健康檢查」（HTTP 探測），
      記錄是否仍可連線、最後檢查時間，藉此及早發現網站改版／下線。
    - 另含選用的「探索模式」：用搜尋引擎找潛在新來源，
      僅列為候選（candidate），需人工確認後才升級為正式來源。

用法：
    python discover_sources.py                 # 健康檢查 + 重建 Satir_list.md
    python discover_sources.py --discover      # 額外跑搜尋探索，附上候選來源
    python discover_sources.py --timeout 15    # 自訂 HTTP 逾時秒數
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("缺少套件 requests，請先執行：pip install requests beautifulsoup4")


# --------------------------------------------------------------------------- #
# 1. 已知來源名冊（核心事實來源，人工維護）
# --------------------------------------------------------------------------- #
# crawler_status 三種值：
#   "ready"    已寫好專屬爬蟲，可實際抓活動
#   "planned"  已確認可爬、結構已勘查，爬蟲待開發
#   "todo"     尚未勘查網站結構
#
# parser_module：未來各網站爬蟲的對應檔名（規劃用，現可留 None）

@dataclass
class Source:
    key: str                       # 唯一代號，作為爬蟲模組命名依據
    name: str                      # 機構全名
    url: str                       # 活動／課程列表頁（爬蟲入口）
    homepage: str                  # 機構首頁
    region: str                    # 主要地區
    notes: str                     # 備註：結構、可爬性、注意事項
    crawler_status: str            # ready / planned / todo
    parser_module: Optional[str] = None
    # 以下為執行期填入的健康檢查結果
    http_status: Optional[int] = field(default=None, init=False)
    reachable: Optional[bool] = field(default=None, init=False)
    checked_at: Optional[str] = field(default=None, init=False)
    error: Optional[str] = field(default=None, init=False)


SEED_SOURCES: list[Source] = [
    Source(
        key="shiuhli",
        name="財團法人旭立文教基金會",
        url="https://www.shiuhli.org.tw/course",
        homepage="https://www.shiuhli.org.tw/",
        region="台北 / 台中",
        notes=(
            "課程列表頁有分類標籤（含「薩提爾」「薩提爾教練」），每筆含日期、"
            "價格、講師與課程連結 /course/TP/{id} 或 /course/TC/{id}；"
            "分頁參數 ?page=N；可加 ?type=available 只看可報名。結構穩定、易爬。"
        ),
        crawler_status="planned",
        parser_module="crawlers/shiuhli.py",
    ),
    Source(
        key="satirtaiwan",
        name="台灣薩提爾人文發展中心",
        url="https://www.satir.com.tw/",
        homepage="https://www.satir.com.tw/",
        region="全台",
        notes="薩提爾模式專門推廣機構，課程多。待勘查列表頁結構。",
        crawler_status="todo",
    ),
    Source(
        key="satirspace",
        name="薩提爾成長模式推廣（張天安／各帶領者）",
        url="https://www.facebook.com/",
        homepage="https://www.facebook.com/",
        region="全台",
        notes=(
            "多數帶領者以 Facebook 公開活動發佈。FB 反爬嚴格且條款受限，"
            "建議以人工補登或僅貼連結，列為低優先。"
        ),
        crawler_status="todo",
    ),
    Source(
        key="caringall",
        name="呂旭立紀念基金會 / 各地家族治療與薩提爾推廣協會",
        url="",
        homepage="",
        region="全台",
        notes="預留欄位：陸續加入各地推廣協會官網。新增來源請在此補上 url 與 homepage。",
        crawler_status="todo",
    ),
]


# --------------------------------------------------------------------------- #
# 2. 健康檢查：探測每個來源是否可連線
# --------------------------------------------------------------------------- #
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SatirEventBot/1.0; "
        "+https://github.com/your-account/satir-events)"
    )
}


def health_check(source: Source, timeout: int) -> None:
    """對來源 url 發 GET，填入 http_status / reachable / checked_at / error。"""
    source.checked_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not source.url:
        source.reachable = None
        source.error = "尚未填入 url"
        return
    try:
        resp = requests.get(source.url, headers=HEADERS, timeout=timeout)
        source.http_status = resp.status_code
        source.reachable = resp.ok
        if not resp.ok:
            source.error = f"HTTP {resp.status_code}"
    except requests.RequestException as exc:
        source.reachable = False
        source.error = type(exc).__name__
    time.sleep(1)  # 友善延遲，避免短時間連發


# --------------------------------------------------------------------------- #
# 3.（選用）探索模式：搜尋潛在新來源，僅列為候選
# --------------------------------------------------------------------------- #
SEARCH_TERMS = [
    "薩提爾 工作坊 報名",
    "Satir 課程 台灣",
    "薩提爾 成長團體",
    "冰山 對話 工作坊",
    "家族治療 薩提爾 講座",
]


def discover_candidates(timeout: int) -> list[dict]:
    """
    用 DuckDuckGo HTML 端點做輕量搜尋，回傳候選來源（網域 + 範例頁）。
    僅供人工檢視，不會自動升級為正式來源。
    需要 beautifulsoup4。
    """
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse, parse_qs, unquote
    except ImportError:
        print("探索模式需要 beautifulsoup4，略過。", file=sys.stderr)
        return []

    known = {urlparse(s.homepage).netloc for s in SEED_SOURCES if s.homepage}
    seen: dict[str, dict] = {}

    for term in SEARCH_TERMS:
        try:
            resp = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": term},
                headers=HEADERS,
                timeout=timeout,
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a.result__a"):
                href = a.get("href", "")
                # DDG 連結常包一層轉址，取出真實 uddg 參數
                qs = parse_qs(urlparse(href).query)
                real = unquote(qs.get("uddg", [href])[0])
                netloc = urlparse(real).netloc
                if not netloc or netloc in known or netloc in seen:
                    continue
                # 過濾常見非機構平台（售票平台另以專屬爬蟲處理）
                if any(p in netloc for p in ("facebook", "youtube", "google", "wikipedia")):
                    continue
                seen[netloc] = {
                    "netloc": netloc,
                    "title": a.get_text(strip=True)[:60],
                    "example_url": real,
                    "found_by": term,
                }
        except requests.RequestException:
            continue
        time.sleep(2)

    return list(seen.values())


# --------------------------------------------------------------------------- #
# 4. 產生 Satir_list.md
# --------------------------------------------------------------------------- #
STATUS_LABEL = {
    "ready": "✅ 已可爬",
    "planned": "🛠 已勘查・待開發",
    "todo": "⬜ 待勘查",
}


def reachable_label(s: Source) -> str:
    if s.reachable is True:
        return f"🟢 可連線 (HTTP {s.http_status})"
    if s.reachable is False:
        return f"🔴 連線失敗 ({s.error})"
    return "⚪ 未檢查"


def build_markdown(sources: list[Source], candidates: list[dict]) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    ready = sum(1 for s in sources if s.crawler_status == "ready")
    planned = sum(1 for s in sources if s.crawler_status == "planned")
    todo = sum(1 for s in sources if s.crawler_status == "todo")

    lines: list[str] = []
    lines.append("# 薩提爾活動 — 來源網站清單（Satir_list.md）")
    lines.append("")
    lines.append(f"> 自動產生於 **{now}**，由 `discover_sources.py` 維護。")
    lines.append(">")
    lines.append("> 這份清單是每日更新流程的第一步：先重建本檔，再依此逐一執行各網站爬蟲更新 `events.json`。")
    lines.append("")
    lines.append(f"**來源統計**：共 {len(sources)} 筆　|　✅ 已可爬 {ready}　🛠 待開發 {planned}　⬜ 待勘查 {todo}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 來源總覽")
    lines.append("")
    lines.append("| 代號 | 機構名稱 | 地區 | 爬蟲狀態 | 連線檢查 | 入口連結 |")
    lines.append("|------|----------|------|----------|----------|----------|")
    for s in sources:
        url_cell = f"[列表頁]({s.url})" if s.url else "—"
        lines.append(
            f"| `{s.key}` | {s.name} | {s.region} | "
            f"{STATUS_LABEL.get(s.crawler_status, s.crawler_status)} | "
            f"{reachable_label(s)} | {url_cell} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 來源細節")
    lines.append("")
    for s in sources:
        lines.append(f"### `{s.key}` — {s.name}")
        lines.append("")
        lines.append(f"- **首頁**：{s.homepage or '（待補）'}")
        lines.append(f"- **爬蟲入口**：{s.url or '（待補）'}")
        lines.append(f"- **主要地區**：{s.region}")
        lines.append(f"- **爬蟲狀態**：{STATUS_LABEL.get(s.crawler_status, s.crawler_status)}")
        if s.parser_module:
            lines.append(f"- **對應爬蟲模組**：`{s.parser_module}`")
        lines.append(f"- **連線檢查**：{reachable_label(s)}　（檢查時間 {s.checked_at or '—'}）")
        lines.append(f"- **備註**：{s.notes}")
        lines.append("")

    if candidates:
        lines.append("---")
        lines.append("")
        lines.append("## 候選來源（探索模式找到，需人工確認）")
        lines.append("")
        lines.append("> 以下為搜尋引擎找到的潛在來源，尚未驗證。確認屬實後，請手動加入 `discover_sources.py` 的 `SEED_SOURCES`。")
        lines.append("")
        lines.append("| 網域 | 標題 | 範例頁 | 搜尋字詞 |")
        lines.append("|------|------|--------|----------|")
        for c in candidates:
            lines.append(
                f"| {c['netloc']} | {c['title']} | [連結]({c['example_url']}) | {c['found_by']} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 如何新增來源")
    lines.append("")
    lines.append("1. 在 `discover_sources.py` 的 `SEED_SOURCES` 新增一筆 `Source(...)`。")
    lines.append("2. 填入 `key`、`name`、`url`（活動列表頁）、`homepage`、`region`、`notes`。")
    lines.append("3. 勘查網站結構後把 `crawler_status` 設為 `planned`，並規劃 `parser_module`。")
    lines.append("4. 寫好專屬爬蟲後改為 `ready`。")
    lines.append("5. 重新執行 `python discover_sources.py` 重建本檔。")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 5. 主程式
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="薩提爾來源網站探索腳本")
    parser.add_argument("--discover", action="store_true", help="額外執行搜尋探索，附上候選來源")
    parser.add_argument("--timeout", type=int, default=12, help="HTTP 逾時秒數（預設 12）")
    parser.add_argument("--output", default="Satir_list.md", help="輸出檔名（預設 Satir_list.md）")
    args = parser.parse_args()

    print(f"開始健康檢查，共 {len(SEED_SOURCES)} 個來源 …")
    for s in SEED_SOURCES:
        health_check(s, args.timeout)
        print(f"  [{s.key}] {reachable_label(s)}")

    candidates: list[dict] = []
    if args.discover:
        print("執行探索模式，搜尋潛在新來源 …")
        candidates = discover_candidates(args.timeout)
        print(f"  找到 {len(candidates)} 個候選網域")

    md = build_markdown(SEED_SOURCES, candidates)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"已寫入 {args.output}（{len(md)} 字元）")


if __name__ == "__main__":
    main()
