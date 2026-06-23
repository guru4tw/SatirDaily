#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawlers/shiuhli.py
===================
旭立文教基金會 課程爬蟲（第一支 parser）。

來源規格見 Satir_source.md 的 `shiuhli` 段：
    入口 https://www.shiuhli.org.tw/course
    列表卡片含薩提爾分類標籤、日期、價格、講師，分頁 ?page=N，結構穩定。

做法（依 Satir_source.md 建議解析路徑）：
    1. 逐頁抓 /course?page=N，解析每張 .course-card：標題、tropism 標籤、講師、日期、價格、連結
    2. 只留 tropism 標籤含「薩提爾」的課程（網站列表是混合分類）
    3. 進每筆 /course/TP/{id} 詳情頁補：地點、講師、時間、費用、學生價、課程簡介(meta description)
    4. 每筆對齊 events.json schema 輸出

無第三方解析依賴（只用 requests + 標準庫 re/html）：本站 markup 乾淨穩定，regex 足夠；
專案目前刻意維持 requests-only。

用法：
    python -m crawlers.shiuhli                 # 抓全部薩提爾課程，印 JSON 到 stdout
    python -m crawlers.shiuhli --out events.json
    python -m crawlers.shiuhli --max-pages 2   # 只抓前兩頁（除錯）
    python -m crawlers.shiuhli --no-detail     # 跳過詳情頁，只取列表欄位（快）
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
KEY = "shiuhli"
SOURCE = "shiuhli"
ORGANIZER = "旭立文教基金會"
BASE = "https://www.shiuhli.org.tw"
LIST_URL = f"{BASE}/course"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SatirEventBot/1.0; "
        "+https://github.com/your-account/satir-events)"
    )
}
REQUEST_DELAY = 1.0       # 友善延遲（秒），沿用 discover_sources 慣例
SATIR_TAG = "薩提爾"

# 課程代號前綴 → 地區（/course/TP/123 → 台北）
REGION_BY_CODE = {
    "TP": "台北", "TC": "台中", "TN": "台南",
    "KH": "高雄", "HC": "新竹", "ONLINE": "線上",
}


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _clean(s: str) -> str:
    """去 HTML tag、解 entity、收斂空白。"""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _get(url: str, timeout: int) -> Optional[str]:
    """GET 一頁，回 HTML 文字；失敗回 None。每次請求後友善延遲。"""
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
# 列表頁解析
# --------------------------------------------------------------------------- #
CARD_RE = re.compile(r'<div class="course-card">(.*?)</div>\s*</div>\s*</div>', re.S)
TP_RE = re.compile(r"/course/([A-Z]+)/(\d+)")
TITLE_RE = re.compile(r'card-title"\s*>\s*<a[^>]*>(.*?)</a>', re.S)
BADGE_RE = re.compile(r'card-tropism-badge[^>]*>(.*?)</span>', re.S)
TEACHER_RE = re.compile(r'card-teacher-name"\s*>(.*?)</div>', re.S)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:\s*-\s*(\d{4}-\d{2}-\d{2}))?")
PRICE_AMOUNT_RE = re.compile(
    r'price-amount"\s*>(.*?)</span>\s*(?=<span class="card-status"|</div>)', re.S)
STATUS_RE = re.compile(r'card-status"\s*>\s*(.*?)\s*</span>', re.S)
PAGE_RE = re.compile(r"/course\?page=(\d+)")


def parse_list_page(htm: str) -> list[dict]:
    """解析一頁列表，回每張卡片的原始欄位（未過濾分類）。"""
    cards: list[dict] = []
    # 用 card-body 為錨切塊比 course-card 收尾穩：每張卡 body 內含全部欄位
    for block in re.split(r'<div class="course-card">', htm)[1:]:
        m_code = TP_RE.search(block)
        if not m_code:
            continue
        code, cid = m_code.group(1), m_code.group(2)
        tags = [_clean(b) for b in BADGE_RE.findall(block)]
        title_m = TITLE_RE.search(block)
        teacher_m = TEACHER_RE.search(block)
        date_m = DATE_RE.search(block)
        price_m = PRICE_AMOUNT_RE.search(block)
        status_m = STATUS_RE.search(block)

        teacher = _clean(teacher_m.group(1)) if teacher_m else ""
        teacher = re.sub(r"^講師\s*", "", teacher)

        cards.append({
            "code": code,
            "id": cid,
            "url": f"{BASE}/course/{code}/{cid}",
            "title": _clean(title_m.group(1)) if title_m else "",
            "tags": tags,
            "facilitator": teacher,
            "date_start": date_m.group(1) if date_m else "",
            "date_end": (date_m.group(2) or date_m.group(1)) if date_m else "",
            "price": _clean(price_m.group(1)) if price_m else "",
            "status": _clean(status_m.group(1)) if status_m else "",
        })
    return cards


def discover_max_page(htm: str) -> int:
    """從分頁列讀最大頁碼；無分頁回 1。"""
    pages = [int(n) for n in PAGE_RE.findall(htm)]
    return max(pages) if pages else 1


# --------------------------------------------------------------------------- #
# 詳情頁解析
# --------------------------------------------------------------------------- #
TOPIC_VIEW_RE = re.compile(
    r'class="topic"\s*>\s*(.*?)\s*</div>\s*<div class="view"[^>]*>(.*?)</div>', re.S)
META_DESC_RE = re.compile(
    r'<meta name="description" content="(.*?)"', re.S)


def parse_detail(htm: str) -> dict:
    """解析詳情頁，回補充欄位（地點/講師/時間/費用/學生價/簡介）。"""
    pairs = {_clean(k): _clean(v) for k, v in TOPIC_VIEW_RE.findall(htm)}
    desc_m = META_DESC_RE.search(htm)
    summary = _clean(html.unescape(desc_m.group(1))) if desc_m else ""
    return {
        "venue": pairs.get("地點", ""),
        "facilitator": pairs.get("講師", ""),
        "time": pairs.get("時間", ""),
        "price": pairs.get("費用", ""),
        "student_price": pairs.get("學生價", ""),
        "summary": summary,
    }


# --------------------------------------------------------------------------- #
# 組裝 events.json 單筆
# --------------------------------------------------------------------------- #
def _format_price(card: dict, detail: dict) -> str:
    base = detail.get("price") or card.get("price") or ""
    base = re.sub(r"NT\s*\$\s*", "NT$ ", base).strip()
    student = detail.get("student_price", "")
    if student:
        student = re.sub(r"NT\s*\$\s*", "NT$ ", student).strip()
        return f"{base}（學生價 {student}）" if base else student
    return base


def to_event(card: dict, detail: dict, fetched_at: str) -> dict:
    venue = detail.get("venue", "")
    # 地點文字優先（離場活動代號仍是 TP，但 venue 會寫實際城市），無則退回代號推導
    region = ""
    for r in ("台北", "新北", "桃園", "新竹", "台中", "台南", "高雄",
              "宜蘭", "花蓮", "台東", "嘉義", "基隆", "線上"):
        if r in venue:
            region = r
            break
    if not region:
        region = REGION_BY_CODE.get(card["code"], "")
    return {
        "id": f"{KEY}-{card['id']}",
        "title": card["title"],
        "purpose": "",                                  # 旭立頁無明確「宗旨」欄，不杜撰
        "summary": detail.get("summary", ""),
        "highlights": [],                               # 無具出處正評，留空（不杜撰）
        "date_start": card["date_start"],
        "date_end": card["date_end"],
        "region": region or "—",
        "venue": venue,
        "facilitator": detail.get("facilitator") or card["facilitator"],
        "organizer": ORGANIZER,
        "price": _format_price(card, detail),
        "signup_url": card["url"],
        "source": SOURCE,
        "fetched_at": fetched_at,
    }


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def crawl(max_pages: Optional[int] = None,
          with_detail: bool = True,
          timeout: int = 15) -> list[dict]:
    """抓全部薩提爾課程，回 events.json schema 的 dict 清單。"""
    fetched_at = dt.datetime.now().strftime("%Y-%m-%d")

    first = _get(LIST_URL, timeout)
    if first is None:
        return []
    total = discover_max_page(first)
    last_page = min(total, max_pages) if max_pages else total
    print(f"[{KEY}] 偵測到 {total} 頁，抓取至第 {last_page} 頁", file=sys.stderr)

    raw_cards: list[dict] = parse_list_page(first)
    for p in range(2, last_page + 1):
        htm = _get(f"{LIST_URL}?page={p}", timeout)
        if htm:
            raw_cards.extend(parse_list_page(htm))

    # 只留薩提爾分類
    cards = [c for c in raw_cards if any(SATIR_TAG in t for t in c["tags"])]
    print(f"[{KEY}] 列表共 {len(raw_cards)} 筆，薩提爾相關 {len(cards)} 筆",
          file=sys.stderr)

    events: list[dict] = []
    for c in cards:
        detail: dict = {}
        if with_detail:
            d_htm = _get(c["url"], timeout)
            if d_htm:
                detail = parse_detail(d_htm)
        events.append(to_event(c, detail, fetched_at))
    return events


def merge_into(path: str, events: list[dict]) -> int:
    """把本來源活動合併進 events.json：去掉舊的同 source 筆，加入新筆，
    依 date_start 排序後寫回。回寫入後總筆數。多來源 pipeline 用，任何
    執行順序都 idempotent，不會清掉別站資料。"""
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
    ap = argparse.ArgumentParser(description="旭立文教基金會 薩提爾課程爬蟲")
    ap.add_argument("--out", nargs="?", const=str(DOCS_DIR / "events.json"),
                    help="寫入檔（給旗標不帶值＝寫 ../../Docs/events.json；完全不給＝印到 stdout）")
    ap.add_argument("--max-pages", type=int, help="只抓前 N 頁（除錯用）")
    ap.add_argument("--no-detail", action="store_true", help="跳過詳情頁，只取列表欄位")
    ap.add_argument("--timeout", type=int, default=15, help="HTTP 逾時秒數（預設 15）")
    args = ap.parse_args()

    events = crawl(
        max_pages=args.max_pages,
        with_detail=not args.no_detail,
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
