#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
discover_sources.py
===================
薩提爾活動 — 來源清單產生器（每日工作的第一步）

職責（單一）：
    讀「人工維護的來源網站清單」Satir_website.md，逐站做連線健康檢查
    與輕量結構偵測，產出 parser 友善的 Satir_source.md。
    本腳本「不」抓取活動內容；抓活動是各網站專屬爬蟲的工作。

分工：
    - Satir_website.md ← 你手改的唯一檔，內容極簡（- [名稱](URL)，可選 | 地區 | 備註）
    - discover_sources.py ← 本腳本，把上面每條連結轉成結構化的下游輸入
    - Satir_source.md ← 自動產物（連線狀態、結構線索、建議解析路徑、parser 模組），勿手改

每日工作流：
    1. python discover_sources.py   ← 讀 Satir_website.md，重建 Satir_source.md
    2. 依 Satir_source.md 逐站執行各網站爬蟲，更新 events.json
    3. 前端（GitHub Pages）讀 events.json 呈現

用法：
    python discover_sources.py                       # 重建 Satir_source.md
    python discover_sources.py --input  其他.md       # 自訂輸入檔
    python discover_sources.py --output 其他.md       # 自訂輸出檔
    python discover_sources.py --timeout 15          # 自訂 HTTP 逾時秒數
    python discover_sources.py --no-fetch            # 只解析清單，不連線（離線排版）
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# 腳本在 Py/，資料檔（Satir_website.md / Satir_source.md）在同層 ../Docs/。
# 預設路徑錨定到 Docs，使腳本不論從哪個 cwd 執行都對得到資料檔。
DOCS_DIR = Path(__file__).resolve().parent.parent / "Docs"

try:
    import requests
except ImportError:
    sys.exit("缺少套件 requests，請先執行：pip install requests")


# --------------------------------------------------------------------------- #
# 1. 資料結構
# --------------------------------------------------------------------------- #
# crawler_status 三種值：
#   "ready"    已寫好專屬爬蟲，可實際抓活動
#   "planned"  已確認可爬、結構已勘查，爬蟲待開發
#   "todo"     尚未勘查（從 Satir_website.md 新加入的預設值）

@dataclass
class Source:
    key: str                       # 由網域自動推導，作為爬蟲模組命名依據
    name: str                      # 機構名稱
    url: str                       # 活動／課程列表頁（爬蟲入口）
    homepage: str                  # 機構首頁（由 url 推導）
    region: str                    # 主要地區
    notes: str                     # 人工備註
    crawler_status: str = "todo"
    parser_module: Optional[str] = None
    # 執行期填入：健康檢查
    http_status: Optional[int] = field(default=None, init=False)
    reachable: Optional[bool] = field(default=None, init=False)
    checked_at: Optional[str] = field(default=None, init=False)
    error: Optional[str] = field(default=None, init=False)
    # 執行期填入：parser 線索（自動偵測，僅供寫爬蟲時參考）
    page_title: Optional[str] = field(default=None, init=False)
    content_type: Optional[str] = field(default=None, init=False)
    hints: list[str] = field(default_factory=list, init=False)
    strategy: list[str] = field(default_factory=list, init=False)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SatirEventBot/1.0; "
        "+https://github.com/your-account/satir-events)"
    )
}


# --------------------------------------------------------------------------- #
# 2. 解析 Satir_website.md（人工維護的輸入）
# --------------------------------------------------------------------------- #
URL_RE = re.compile(r"https?://[^\s|)\]]+")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def derive_key(url: str, taken: set[str]) -> str:
    """由網域推導唯一代號：www.shiuhli.org.tw -> shiuhli。"""
    netloc = urlparse(url).netloc.lower()
    netloc = netloc.split(":")[0]
    labels = [p for p in netloc.split(".") if p not in ("www", "")]
    base = re.sub(r"[^a-z0-9]", "", labels[0]) if labels else "source"
    base = base or "source"
    key = base
    # 撞名先用網域第二段（com/org/...）區分，再退而用流水號
    if key in taken and len(labels) > 1:
        key = f"{base}_{re.sub(r'[^a-z0-9]', '', labels[1])}"
    n = 2
    while key in taken:
        key = f"{base}{n}"
        n += 1
    taken.add(key)
    return key


def parse_website_md(path: str) -> list[Source]:
    """讀 Satir_website.md，回傳 Source 清單。格式見該檔頂端說明。"""
    try:
        with open(path, encoding="utf-8") as f:
            raw_lines = f.readlines()
    except FileNotFoundError:
        sys.exit(
            f"找不到輸入檔 {path}。\n"
            f"請建立 {path}，一行一個來源（名稱 | URL | 地區 | 備註）。"
        )

    sources: list[Source] = []
    taken: set[str] = set()
    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[-*]\s+", "", line)        # 去掉 markdown 清單符號

        name, url, region, notes = "", "", "", ""
        md = MD_LINK_RE.search(line)
        if md:
            # markdown 連結格式： [名稱](URL)  其後可接 | 地區 | 備註
            name = md.group(1).strip()
            url = md.group(2).strip()
            rest = [p.strip() for p in line[md.end():].split("|") if p.strip()]
            region = rest[0] if rest else ""
            notes = " ".join(rest[1:])
        else:
            # 純文字管線格式： 名稱 | URL | 地區 | 備註
            m = URL_RE.search(line)
            if not m:
                print(f"  跳過（找不到 URL）：{line[:50]}", file=sys.stderr)
                continue
            url = m.group(0).rstrip("/),。")
            parts = [p.strip() for p in line.split("|")]
            url_idx = next((i for i, p in enumerate(parts) if URL_RE.search(p)), 0)
            name = " ".join(parts[:url_idx]).strip()
            region = parts[url_idx + 1].strip() if len(parts) > url_idx + 1 else ""
            notes = " ".join(parts[url_idx + 2:]).strip()

        parsed = urlparse(url)
        homepage = f"{parsed.scheme}://{parsed.netloc}/"
        key = derive_key(url, taken)
        if not name:
            name = parsed.netloc

        sources.append(Source(
            key=key,
            name=name,
            url=url,
            homepage=homepage,
            region=region or "—",
            notes=notes,
            crawler_status="todo",
            parser_module=f"crawlers/{key}.py",
        ))
    return sources


# --------------------------------------------------------------------------- #
# 3. 健康檢查 + 結構偵測（一次請求兼得）
# --------------------------------------------------------------------------- #
def detect_hints(url: str, html: str) -> list[str]:
    """從回應 HTML 抓 parser 線索（僅供寫爬蟲時參考，非保證）。"""
    hints: list[str] = []
    low = html.lower()
    if "wp-content" in low or "wp-json" in low:
        hints.append("疑似 WordPress（可試 /wp-json REST API）")
    if "accupass" in urlparse(url).netloc:
        hints.append("Accupass 售票平台（查公開 API / 動態載入）")
    if re.search(r"[?&]page=\d", html) or "/page/" in low:
        hints.append("偵測到分頁樣式（?page= 或 /page/）")
    if "application/ld+json" in low:
        hints.append("含 JSON-LD 結構化資料（可直接取 Event schema）")
    if "<table" in low:
        hints.append("頁面含 <table>，列表可能為表格")
    return hints


def suggest_strategy(url: str, hints: list[str]) -> list[str]:
    """把偵測線索合成「建議解析路徑」，依優先序排，給 parser 開發者。"""
    h = " ".join(hints)
    steps: list[str] = []
    if "JSON-LD" in h:
        steps.append("優先：抓 <script type=application/ld+json>，取 schema.org Event/Course 結構化欄位")
    if "WordPress" in h:
        steps.append("次選：試 REST API /wp-json/wp/v2/posts（或自訂 post type），回 JSON 免解 HTML")
    if "Accupass" in h:
        steps.append("此為售票平台：改打其搜尋 API / 觀察 XHR，勿硬解靜態 HTML")
    if "<table>" in h:
        steps.append("HTML 列表在 <table>：逐 <tr> 取欄位（日期/標題/連結）")
    if not steps:
        steps.append("解析 HTML：找重複的活動卡片區塊，逐塊取標題/日期/連結")
    if "分頁" in h:
        steps.append("分頁：沿 ?page= 或 /page/ 遞增直到無新資料")
    steps.append("每筆對齊 events.json schema（id/title/date_start/region/signup_url/...）")
    return steps


def health_check(source: Source, timeout: int) -> None:
    """對來源 url 發 GET，填入連線結果與 parser 線索。"""
    source.checked_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not source.url:
        source.reachable = None
        source.error = "尚未填入 url"
        return
    try:
        resp = requests.get(source.url, headers=HEADERS, timeout=timeout)
        source.http_status = resp.status_code
        source.reachable = resp.ok
        source.content_type = resp.headers.get("Content-Type", "").split(";")[0] or None
        if resp.ok:
            html = resp.text
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            if m:
                source.page_title = re.sub(r"\s+", " ", m.group(1)).strip()[:80]
            source.hints = detect_hints(source.url, html)
            source.strategy = suggest_strategy(source.url, source.hints)
        else:
            source.error = f"HTTP {resp.status_code}"
    except requests.RequestException as exc:
        source.reachable = False
        source.error = type(exc).__name__
    time.sleep(1)  # 友善延遲，避免短時間連發


# --------------------------------------------------------------------------- #
# 4. 產生 Satir_source.md（parser 友善）
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


def build_markdown(sources: list[Source], input_path: str) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    ready = sum(1 for s in sources if s.crawler_status == "ready")
    planned = sum(1 for s in sources if s.crawler_status == "planned")
    todo = sum(1 for s in sources if s.crawler_status == "todo")
    online = sum(1 for s in sources if s.reachable is True)

    L: list[str] = []
    L.append("# 薩提爾活動 — 來源規格（Satir_source.md）")
    L.append("")
    L.append(f"> 自動產生於 **{now}**，由 `discover_sources.py` 讀 `{input_path}` 產出。")
    L.append("> **本檔為自動產物，請勿手改**；要增刪來源請改 "
             f"`{input_path}`，再重跑腳本。")
    L.append(">")
    L.append("> 用途：每個來源在「來源細節」段提供 **入口、連線狀態、結構線索、"
             "建議解析路徑、對應 parser 模組**，讓各網站專屬爬蟲知道怎麼抓。")
    L.append("")
    L.append(f"**統計**：共 {len(sources)} 筆　|　🟢 可連線 {online}　|　"
             f"✅ 已可爬 {ready}　🛠 待開發 {planned}　⬜ 待勘查 {todo}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 來源總覽")
    L.append("")
    L.append("| 代號 | 機構名稱 | 地區 | 爬蟲狀態 | 連線檢查 | 入口連結 |")
    L.append("|------|----------|------|----------|----------|----------|")
    for s in sources:
        url_cell = f"[列表頁]({s.url})" if s.url else "—"
        L.append(
            f"| `{s.key}` | {s.name} | {s.region} | "
            f"{STATUS_LABEL.get(s.crawler_status, s.crawler_status)} | "
            f"{reachable_label(s)} | {url_cell} |"
        )
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 來源細節（供 parser 開發）")
    L.append("")
    for s in sources:
        L.append(f"### `{s.key}` — {s.name}")
        L.append("")
        L.append(f"- **首頁**：{s.homepage or '（待補）'}")
        L.append(f"- **爬蟲入口**：{s.url or '（待補）'}")
        L.append(f"- **主要地區**：{s.region}")
        L.append(f"- **爬蟲狀態**：{STATUS_LABEL.get(s.crawler_status, s.crawler_status)}")
        L.append(f"- **建議爬蟲模組**：`{s.parser_module}`")
        L.append(f"- **連線檢查**：{reachable_label(s)}　（檢查時間 {s.checked_at or '—'}）")
        if s.content_type:
            L.append(f"- **Content-Type**：`{s.content_type}`")
        if s.page_title:
            L.append(f"- **頁面標題**：{s.page_title}")
        if s.hints:
            L.append(f"- **結構線索（自動偵測，需人工確認）**：{'；'.join(s.hints)}")
        if s.strategy:
            L.append("- **建議解析路徑**：")
            for i, step in enumerate(s.strategy, 1):
                L.append(f"    {i}. {step}")
        if s.notes:
            L.append(f"- **人工備註**：{s.notes}")
        L.append("")

    L.append("---")
    L.append("")
    L.append("## 如何新增來源")
    L.append("")
    L.append(f"1. 在 `{input_path}` 加一行：`- [名稱](入口URL)`（其後可接 ` | 地區 | 備註`，只有 URL 必填）。")
    L.append("2. 重跑 `python discover_sources.py` 重建本檔，看連線、結構線索與建議解析路徑。")
    L.append("3. 依該來源的「建議解析路徑」開發對應 `crawlers/<代號>.py`。")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# 5. 主程式
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="薩提爾來源清單產生器")
    ap.add_argument("--input", default=str(DOCS_DIR / "Satir_website.md"),
                    help="輸入清單（預設 ../Docs/Satir_website.md）")
    ap.add_argument("--output", default=str(DOCS_DIR / "Satir_source.md"),
                    help="輸出檔（預設 ../Docs/Satir_source.md）")
    ap.add_argument("--timeout", type=int, default=12, help="HTTP 逾時秒數（預設 12）")
    ap.add_argument("--no-fetch", action="store_true", help="不連線，只解析清單與排版")
    args = ap.parse_args()

    sources = parse_website_md(args.input)
    print(f"自 {args.input} 解析出 {len(sources)} 個來源。")

    if not args.no_fetch:
        print("開始連線檢查與結構偵測 …")
        for s in sources:
            health_check(s, args.timeout)
            extra = f"｜{'；'.join(s.hints)}" if s.hints else ""
            print(f"  [{s.key}] {reachable_label(s)}{extra}")

    md = build_markdown(sources, args.input)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"已寫入 {args.output}（{len(md)} 字元）")


if __name__ == "__main__":
    main()
