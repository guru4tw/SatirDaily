#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawlers/lopwilldo.py
=====================
長耳兔心靈維度 活動爬蟲（第二支 parser）。

來源規格見 Satir_source.md 的 `lopwilldo` 段。實勘結果與自動偵測不同：
首頁 JSON-LD 只有 Yoast SEO 樣板（無 Event schema），但站台用
The Events Calendar 外掛，活動全在其 REST API：

    GET /wp-json/tribe/events/v1/events?per_page=50&start_date=...&status=publish

回傳結構化欄位（title/start_date/end_date/url/cost/venue/organizer/
description/tags/categories），免解 HTML，最穩。

做法：
    1. 打 tribe events API，分頁抓全部已發布活動（start_date 拉到很早以涵蓋全部）
    2. 只留 title/description/tag 含「薩提爾」的活動（站內仍有非薩提爾課程）
    3. 每筆對齊 events.json schema 輸出

無第三方解析依賴（只用 requests + 標準庫）：API 回 JSON，標準庫足夠。

用法：
    python -m crawlers.lopwilldo                 # 抓全部薩提爾活動，印 JSON 到 stdout
    python -m crawlers.lopwilldo --out           # 合併寫入 ../../Docs/events.json
    python -m crawlers.lopwilldo --max-pages 1   # 只抓第一頁（除錯）
    python -m crawlers.lopwilldo --all           # 不過濾薩提爾，輸出全部活動
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

# 套件在 Py/crawlers/，資料檔（events.json）落在 ../../Docs/。
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "Docs"

try:
    import requests
except ImportError:
    sys.exit("缺少套件 requests，請先執行：pip install requests")


# --------------------------------------------------------------------------- #
# 設定
# --------------------------------------------------------------------------- #
KEY = "lopwilldo"
SOURCE = "lopwilldo"
ORGANIZER = "長耳兔心靈維度"
BASE = "https://lopwilldo.com"
API = f"{BASE}/wp-json/tribe/events/v1/events"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SatirEventBot/1.0; "
        "+https://github.com/your-account/satir-events)"
    )
}
REQUEST_DELAY = 1.0       # 友善延遲（秒），沿用專案慣例
SATIR_TAG = "薩提爾"
PER_PAGE = 50             # tribe API 上限，51 筆活動兩頁可抓完
EARLY_DATE = "2000-01-01"  # start_date 拉早以涵蓋全部活動（前端再依日期排序）

# 區域偵測用城市清單（venue/address/title 任一命中即採）
REGIONS = ("台北", "新北", "桃園", "新竹", "苗栗", "台中", "彰化", "南投",
           "雲林", "嘉義", "台南", "高雄", "屏東", "宜蘭", "花蓮", "台東",
           "基隆", "線上")


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _clean(s: str) -> str:
    """去 HTML tag、解 entity、收斂空白。"""
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _get_json(url: str, timeout: int) -> Optional[dict]:
    """GET 一頁 JSON；失敗回 None。每次請求後友善延遲。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  連線/解析失敗 {url}：{type(exc).__name__}", file=sys.stderr)
        return None
    finally:
        time.sleep(REQUEST_DELAY)


# --------------------------------------------------------------------------- #
# 欄位萃取
# --------------------------------------------------------------------------- #
def _venue_name(ev: dict) -> str:
    """tribe venue 是 dict（無場地時為 list）；取場地名稱與地址。"""
    v = ev.get("venue")
    if isinstance(v, dict):
        seen: list[str] = []
        for p in (v.get("venue", ""), v.get("address", ""), v.get("city", "")):
            p = _clean(p)
            if p and p not in seen:
                seen.append(p)
        return " ".join(seen)
    return ""


def _organizer_name(ev: dict) -> str:
    org = ev.get("organizer")
    if isinstance(org, list) and org and isinstance(org[0], dict):
        return _clean(org[0].get("organizer", "")) or ORGANIZER
    if isinstance(org, dict):
        return _clean(org.get("organizer", "")) or ORGANIZER
    return ORGANIZER


def _tag_names(ev: dict) -> list[str]:
    tags = ev.get("tags")
    out: list[str] = []
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, dict) and t.get("name"):
                out.append(_clean(t["name"]))
    return out


def _is_satir(ev: dict, title: str, summary: str) -> bool:
    if SATIR_TAG in title or SATIR_TAG in summary:
        return True
    return any(SATIR_TAG in t for t in _tag_names(ev))


def _region(text: str) -> str:
    for r in REGIONS:
        if r in text:
            return r
    return ""


def to_event(ev: dict, fetched_at: str) -> dict:
    title = _clean(ev.get("title", ""))
    summary = _clean(ev.get("description") or ev.get("excerpt") or "")
    venue = _venue_name(ev)
    region = _region(venue) or _region(title) or _region(summary) or "—"
    return {
        "id": f"{KEY}-{ev.get('id')}",
        "title": title,
        "purpose": "",                       # tribe 無「宗旨」欄，不杜撰
        "summary": summary,
        "highlights": [],                    # 無具出處正評，留空（不杜撰）
        "date_start": (ev.get("start_date") or "")[:10],
        "date_end": (ev.get("end_date") or "")[:10],
        "region": region,
        "venue": venue,
        "facilitator": "",                   # tribe 無講師欄（tag 多為人名但不保證），不杜撰
        "organizer": _organizer_name(ev),
        "price": _clean(ev.get("cost", "")),
        "signup_url": ev.get("url", ""),
        "source": SOURCE,
        "fetched_at": fetched_at,
    }


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def crawl(max_pages: Optional[int] = None,
          satir_only: bool = True,
          timeout: int = 20) -> list[dict]:
    """抓全部活動，回 events.json schema 的 dict 清單。"""
    fetched_at = dt.datetime.now().strftime("%Y-%m-%d")

    first = _get_json(
        f"{API}?per_page={PER_PAGE}&page=1"
        f"&start_date={EARLY_DATE}&status=publish", timeout)
    if first is None:
        return []
    total_pages = int(first.get("total_pages") or 1)
    last_page = min(total_pages, max_pages) if max_pages else total_pages
    print(f"[{KEY}] 偵測到 {first.get('total')} 筆 / {total_pages} 頁，"
          f"抓取至第 {last_page} 頁", file=sys.stderr)

    raw: list[dict] = list(first.get("events", []))
    for p in range(2, last_page + 1):
        d = _get_json(
            f"{API}?per_page={PER_PAGE}&page={p}"
            f"&start_date={EARLY_DATE}&status=publish", timeout)
        if d:
            raw.extend(d.get("events", []))

    events: list[dict] = []
    kept = 0
    for ev in raw:
        title = _clean(ev.get("title", ""))
        summary = _clean(ev.get("description") or ev.get("excerpt") or "")
        if satir_only and not _is_satir(ev, title, summary):
            continue
        kept += 1
        events.append(to_event(ev, fetched_at))
    print(f"[{KEY}] 共 {len(raw)} 筆，"
          f"{'薩提爾相關 ' + str(kept) if satir_only else '全部 ' + str(kept)} 筆",
          file=sys.stderr)
    return events


def merge_into(path: str, events: list[dict]) -> int:
    """把本來源活動合併進 events.json：去掉舊的同 source 筆，加入新筆，
    依 date_start 排序後寫回。回寫入後總筆數。"""
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
    ap = argparse.ArgumentParser(description="長耳兔心靈維度 薩提爾活動爬蟲")
    ap.add_argument("--out", nargs="?", const=str(DOCS_DIR / "events.json"),
                    help="合併寫入檔（給旗標不帶值＝寫 ../../Docs/events.json；"
                         "完全不給＝印到 stdout）")
    ap.add_argument("--max-pages", type=int, help="只抓前 N 頁（除錯用）")
    ap.add_argument("--all", action="store_true",
                    help="不過濾薩提爾，輸出全部活動")
    ap.add_argument("--timeout", type=int, default=20, help="HTTP 逾時秒數（預設 20）")
    args = ap.parse_args()

    events = crawl(
        max_pages=args.max_pages,
        satir_only=not args.all,
        timeout=args.timeout,
    )
    if args.out:
        total = merge_into(args.out, events)
        print(f"[{KEY}] 已合併寫入 {args.out}（本來源 {len(events)} 筆，"
              f"全檔共 {total} 筆）", file=sys.stderr)
    else:
        print(json.dumps(events, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
