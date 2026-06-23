#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawlers/omia.py
================
OMIA 學東西（www.omia.com.tw）薩提爾線上課程爬蟲。

實勘結果（與 Satir_source.md 自動偵測不同）：
- 非 WordPress；首頁 JSON-LD 只有 Organization/WebSite 樣板，無 Event schema。
- 搜尋頁 /searchProject/<關鍵字> 為伺服器端渲染，drupalSettings 內嵌
  "cardList" JSON 陣列，含每門課的 nid/projectTitle/projectUrl/authorName/
  finalPrice/originalPrice/viewCount。
- 薩提爾關鍵字目前命中 2 門李崇建線上課（《薩提爾的對話練習》系列）。
  皆為隨到隨學的線上課程，無固定日期，date_start 留空（不杜撰），
  venue 記「線上課程」。

故本 parser：
    1. 抓 /searchProject/薩提爾，從內嵌 cardList JSON 取每門課欄位
    2. 進每門課程頁取 meta description 當摘要
    3. 每筆對齊 events.json schema

無第三方解析依賴（只用 requests + 標準庫）。

用法：
    python Py/crawlers/omia.py            # 印 JSON 到 stdout
    python Py/crawlers/omia.py --out      # 合併寫入 Docs/events.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "Docs"

try:
    import requests
except ImportError:
    sys.exit("缺少套件 requests，請先執行：pip install requests")


# --------------------------------------------------------------------------- #
# 設定
# --------------------------------------------------------------------------- #
KEY = "omia"
SOURCE = "omia"
ORGANIZER = "OMIA 學東西"
BASE = "https://www.omia.com.tw"
KEYWORD = "薩提爾"
SEARCH_URL = BASE + "/searchProject/" + quote(KEYWORD)
ONLINE_VENUE = "線上課程"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SatirEventBot/1.0; "
        "+https://github.com/your-account/satir-events)"
    )
}
REQUEST_DELAY = 1.0


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _clean(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _get(url: str, timeout: int) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        print(f"  連線失敗 {url}：{type(exc).__name__}", file=sys.stderr)
        return None
    finally:
        time.sleep(REQUEST_DELAY)


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
META_DESC_RE = re.compile(r'<meta name="description" content="(.*?)"', re.S)


def _extract_cardlist(htm: str) -> list[dict]:
    """從 drupalSettings 的 "cardList":[...] 取出所有含 nid 的課程 dict。

    cardList 可能多層巢狀（[[card, ...], ...]），故遞迴收集所有 nid 物件。
    """
    i = htm.find('"cardList":')
    if i < 0:
        return []
    start = htm.index("[", i)
    depth = 0
    end = -1
    for k in range(start, len(htm)):
        c = htm[k]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    if end < 0:
        return []
    try:
        data = json.loads(htm[start:end])
    except ValueError:
        return []

    cards: list[dict] = []
    seen: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            nid = node.get("nid")
            if nid and node.get("projectTitle") and nid not in seen:
                seen.add(nid)
                cards.append(node)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(data)
    return cards


def _price(card: dict) -> str:
    p = card.get("finalPrice") or card.get("originalPrice")
    return f"{p}元" if p else ""


def to_event(card: dict, summary: str, fetched_at: str) -> dict:
    return {
        "id": f"{KEY}-{card['nid']}",
        "title": _clean(card.get("projectTitle", "")),
        "purpose": "",
        "summary": summary,
        "highlights": [],
        "date_start": "",                    # 隨到隨學線上課，無固定日期，不杜撰
        "date_end": "",
        "region": "—",
        "venue": ONLINE_VENUE,
        "facilitator": _clean(card.get("authorName", "")),
        "organizer": ORGANIZER,
        "price": _price(card),
        "signup_url": card.get("projectUrl", "").split("?", 1)[0],
        "source": SOURCE,
        "fetched_at": fetched_at,
    }


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def crawl(timeout: int = 20) -> list[dict]:
    fetched_at = dt.datetime.now().strftime("%Y-%m-%d")
    htm = _get(SEARCH_URL, timeout)
    if htm is None:
        return []
    cards = _extract_cardlist(htm)
    print(f"[{KEY}] 搜尋「{KEYWORD}」取得 {len(cards)} 門課", file=sys.stderr)

    events: list[dict] = []
    for c in cards:
        url = c.get("projectUrl", "")
        summary = ""
        if url:
            d_htm = _get(url, timeout)
            if d_htm:
                m = META_DESC_RE.search(d_htm)
                if m:
                    summary = _clean(html.unescape(m.group(1)))
        events.append(to_event(c, summary, fetched_at))
    return events


def merge_into(path: str, events: list[dict]) -> int:
    existing: list[dict] = []
    p = Path(path)
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            existing = []
    merged = [e for e in existing if e.get("source") != SOURCE] + events
    merged.sort(key=lambda e: e.get("date_start") or "")
    p.write_text(json.dumps(merged, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return len(merged)


def main() -> None:
    ap = argparse.ArgumentParser(description="OMIA 學東西 薩提爾線上課程爬蟲")
    ap.add_argument("--out", nargs="?", const=str(DOCS_DIR / "events.json"),
                    help="合併寫入檔（給旗標不帶值＝寫 Docs/events.json）")
    ap.add_argument("--timeout", type=int, default=20, help="HTTP 逾時秒數（預設 20）")
    args = ap.parse_args()

    events = crawl(timeout=args.timeout)
    if args.out:
        total = merge_into(args.out, events)
        print(f"[{KEY}] 已合併寫入 {args.out}（本來源 {len(events)} 筆，"
              f"全檔共 {total} 筆）", file=sys.stderr)
    else:
        print(json.dumps(events, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
