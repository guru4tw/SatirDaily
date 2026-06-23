#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawlers/comflow.py
===================
心流逸境教育平台 薩提爾課程爬蟲（第三支 parser）。

來源規格見 Satir_source.md 的 `comflow` 段。實勘結果與自動偵測不同：
- 首頁/分類頁 JSON-LD 只有 Yoast SEO 樣板（無 Event schema）
- 自訂課程型別 `academy_courses` 不開放 REST（/wp-json/.../academy_courses 回 404）
- 薩提爾分類頁 /category/活動/薩提爾/ 只有三篇常設課程（初階/進階/高階），
  課程頁標「日期：依報名場次」——無固定活動日期，屬循環開課

故本 parser：
    1. 抓薩提爾分類頁，取每篇 <article> 的課程連結與標題
    2. 進每篇課程頁，取 meta description（摘要）、講師、一般票價格
    3. date_start/date_end 留空（依報名場次，不杜撰日期），
       venue 記「依報名場次」，每筆對齊 events.json schema

無第三方解析依賴（只用 requests + 標準庫）。

用法：
    python crawlers/comflow.py            # 印 JSON 到 stdout
    python crawlers/comflow.py --out      # 合併寫入 ../../Docs/events.json
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

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "Docs"

try:
    import requests
except ImportError:
    sys.exit("缺少套件 requests，請先執行：pip install requests")


# --------------------------------------------------------------------------- #
# 設定
# --------------------------------------------------------------------------- #
KEY = "comflow"
SOURCE = "comflow"
ORGANIZER = "心流逸境教育平台"
BASE = "https://comflow.tw"
CAT_URL = (BASE + "/category/%E6%B4%BB%E5%8B%95/%E8%96%A9%E6%8F%90%E7%88%BE")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SatirEventBot/1.0; "
        "+https://github.com/your-account/satir-events)"
    )
}
REQUEST_DELAY = 1.0
SATIR_TAG = "薩提爾"
NO_DATE_VENUE = "依報名場次"


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
ARTICLE_RE = re.compile(r"<article[^>]*>(.*?)</article>", re.S)
CARD_LINK_RE = re.compile(
    r'<h[1-4][^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
META_DESC_RE = re.compile(r'<meta name="description" content="(.*?)"', re.S)
TEACHER_RE = re.compile(r"講師[：:]\s*([^<（(]{1,40})")
PRICE_RE = re.compile(r"一般票[：:]?(.{0,200}?)(?:</li>|</p>|加入購物車|立即報名)", re.S)
PRICE_NUM_RE = re.compile(r"(NT\$?\s*[\d,]+|\d[\d,]{2,}\s*元)")


def list_courses(htm: str) -> list[dict]:
    """從分類頁取每篇課程的 url + 標題。"""
    out: list[dict] = []
    seen: set[str] = set()
    for block in ARTICLE_RE.findall(htm):
        m = CARD_LINK_RE.search(block)
        if not m:
            continue
        url = m.group(1).strip()
        if url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "title": _clean(m.group(2))})
    return out


def parse_course(htm: str) -> dict:
    """從課程頁取摘要、講師、一般票價格。"""
    desc_m = META_DESC_RE.search(htm)
    teacher_m = TEACHER_RE.search(htm)
    price_m = PRICE_RE.search(htm)
    price = ""
    if price_m:
        pm = PRICE_NUM_RE.search(_clean(price_m.group(1)))
        if pm:
            price = pm.group(1).strip()
    return {
        "summary": _clean(html.unescape(desc_m.group(1))) if desc_m else "",
        "facilitator": _clean(teacher_m.group(1)) if teacher_m else "",
        "price": price,
    }


def _course_id(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    return slug or "course"


def to_event(card: dict, detail: dict, fetched_at: str) -> dict:
    return {
        "id": f"{KEY}-{_course_id(card['url'])}",
        "title": card["title"],
        "purpose": "",
        "summary": detail.get("summary", ""),
        "highlights": [],
        "date_start": "",                    # 依報名場次，無固定日期，不杜撰
        "date_end": "",
        "region": "—",
        "venue": NO_DATE_VENUE,
        "facilitator": detail.get("facilitator", ""),
        "organizer": ORGANIZER,
        "price": detail.get("price", ""),
        "signup_url": card["url"],
        "source": SOURCE,
        "fetched_at": fetched_at,
    }


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def crawl(timeout: int = 20) -> list[dict]:
    fetched_at = dt.datetime.now().strftime("%Y-%m-%d")
    htm = _get(CAT_URL, timeout)
    if htm is None:
        return []
    cards = list_courses(htm)
    # 只留標題含薩提爾（分類頁理應全是，保險過濾）
    cards = [c for c in cards if SATIR_TAG in c["title"]] or cards
    print(f"[{KEY}] 分類頁取得 {len(cards)} 篇課程", file=sys.stderr)

    events: list[dict] = []
    for c in cards:
        d_htm = _get(c["url"], timeout)
        detail = parse_course(d_htm) if d_htm else {}
        events.append(to_event(c, detail, fetched_at))
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
    ap = argparse.ArgumentParser(description="心流逸境 薩提爾課程爬蟲")
    ap.add_argument("--out", nargs="?", const=str(DOCS_DIR / "events.json"),
                    help="合併寫入檔（給旗標不帶值＝寫 ../../Docs/events.json）")
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
