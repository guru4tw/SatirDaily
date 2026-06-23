#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawlers/satir_org.py
=====================
台灣薩提爾成長模式推展協會（www.satir.org.tw）課程爬蟲。

實勘結果（與 Satir_source.md 自動偵測不同）：
- 非 WordPress（無 /wp-json）；首頁 JSON-LD 只有 Yoast 樣板（Organization/WebSite），
  無 Event schema。
- 真正課程清單在 /schedule，依地區分頁：/schedule/class/<region>，
  每頁列該區課程連結 /schedule/class/<region>/<slug>。
- 課程詳情頁 /schedule/<slug>（Joomla EventBooking 外掛，class="eb-event-*"），
  結構化欄位齊全：課程日期、截止日期、課程費用、講師、課程時間，內文含「地點：」。

故本 parser：
    1. 逐地區清單頁取 slug + 標題 + 地區
    2. 進每篇詳情頁 /schedule/<slug>，解 eb-event 欄位與內文地點
    3. 課程日期「2026-06-26 9:30 am~2026-06-28 5:00 pm」拆成 date_start/date_end
       （拆不出就留空，不杜撰），每筆對齊 events.json schema

無第三方解析依賴（只用 requests + 標準庫）。

用法：
    python Py/crawlers/satir_org.py            # 印 JSON 到 stdout
    python Py/crawlers/satir_org.py --out      # 合併寫入 Docs/events.json
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
KEY = "satir_org"
SOURCE = "satir_org"
ORGANIZER = "台灣薩提爾成長模式推展協會"
BASE = "https://www.satir.org.tw"

# 地區清單頁 path -> 地區標籤（取自 /schedule 頁分區）
REGIONS = {
    "north": "台北",
    "hsinchu": "桃竹",
    "taichung": "中彰投",
    "tainan": "雲嘉南",
    "hualieng": "宜花東",
    "kaohsiung": "高屏",
    "online-professional": "線上",
    "jiao-shi-gong-yi": "公益",
}

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
EB_PROP_RE = re.compile(
    r'<aside class="eb-event-property-label">(.*?)</aside>\s*'
    r'<aside class="eb-event-property-value[^"]*">(.*?)</aside>', re.S)
COURSE_DATE_RE = re.compile(
    r"課程日期\s*</h3>.*?eb-event-property-value[^>]*>\s*(.*?)</aside>", re.S)
DATE_RANGE_RE = re.compile(
    r"(\d{4})-(\d{1,2})-(\d{1,2}).*?~.*?(\d{4})-(\d{1,2})-(\d{1,2})", re.S)
SINGLE_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
LOCATION_RE = re.compile(r"地\s*點[：:]\s*([^。\n<]{4,80})")
# 地點常與下一條編號項（「十、…」）連寫，無句點分隔，於此截斷
VENUE_TAIL_RE = re.compile(r"\s*(?:[一二三四五六七八九十]、|備註|注意|感謝).*$")
PRICE_NUM_RE = re.compile(r"(原價\s*[\d,]+\s*元|NT\$?\s*[\d,]+|\d[\d,]{2,}\s*元)")


def list_region(region_path: str, timeout: int) -> list[dict]:
    """取單一地區清單頁的課程 slug + 標題。"""
    url = f"{BASE}/schedule/class/{region_path}"
    htm = _get(url, timeout)
    if htm is None:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    link_re = re.compile(
        r'<a[^>]*href="(/schedule/class/' + re.escape(region_path) +
        r'/([^"/]+))"[^>]*>(.*?)</a>', re.S)
    for m in link_re.finditer(htm):
        slug = m.group(2)
        title = _clean(m.group(3))
        if slug in seen or not title:
            continue
        seen.add(slug)
        out.append({"slug": slug, "title": title,
                    "region": REGIONS.get(region_path, "—")})
    return out


def _iso(y: str, m: str, d: str) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def parse_detail(htm: str) -> dict:
    """從詳情頁取日期、講師、費用、課程時間、地點。"""
    props: dict[str, str] = {}
    for label, value in EB_PROP_RE.findall(htm):
        props[_clean(label)] = _clean(value)

    date_start = date_end = ""
    m = COURSE_DATE_RE.search(htm)
    date_text = _clean(m.group(1)) if m else ""
    rng = DATE_RANGE_RE.search(date_text)
    if rng:
        date_start = _iso(*rng.group(1, 2, 3))
        date_end = _iso(*rng.group(4, 5, 6))
    else:
        one = SINGLE_DATE_RE.search(date_text)
        if one:
            date_start = date_end = _iso(*one.group(1, 2, 3))

    flat = _clean(htm)
    loc_m = LOCATION_RE.search(flat)
    venue = _clean(loc_m.group(1)) if loc_m else ""
    venue = VENUE_TAIL_RE.sub("", venue).strip()

    price = ""
    price_text = props.get("課程費用", "")
    pm = PRICE_NUM_RE.search(price_text or flat)
    if pm:
        price = pm.group(1).strip()

    return {
        "date_start": date_start,
        "date_end": date_end,
        "facilitator": props.get("講師", ""),
        "course_time": props.get("課程時間", ""),
        "venue": venue,
        "price": price,
    }


def to_event(card: dict, detail: dict, fetched_at: str) -> dict:
    return {
        "id": f"{KEY}-{card['slug']}",
        "title": card["title"],
        "purpose": "",
        "summary": detail.get("course_time", ""),
        "highlights": [],
        "date_start": detail.get("date_start", ""),
        "date_end": detail.get("date_end", ""),
        "region": card.get("region", "—"),
        "venue": detail.get("venue", ""),
        "facilitator": detail.get("facilitator", ""),
        "organizer": ORGANIZER,
        "price": detail.get("price", ""),
        "signup_url": f"{BASE}/schedule/{card['slug']}",
        "source": SOURCE,
        "fetched_at": fetched_at,
    }


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def crawl(timeout: int = 20) -> list[dict]:
    fetched_at = dt.datetime.now().strftime("%Y-%m-%d")
    cards: dict[str, dict] = {}
    for region_path in REGIONS:
        for c in list_region(region_path, timeout):
            cards.setdefault(c["slug"], c)  # 同 slug 跨區只留首見
    print(f"[{KEY}] 各地區清單共取得 {len(cards)} 門課", file=sys.stderr)

    events: list[dict] = []
    for c in cards.values():
        htm = _get(f"{BASE}/schedule/{c['slug']}", timeout)
        detail = parse_detail(htm) if htm else {}
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
    ap = argparse.ArgumentParser(description="台灣薩提爾成長模式推展協會 課程爬蟲")
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
