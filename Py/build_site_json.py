#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_site_json.py
==================
把爬蟲產出的 Docs/events.json(扁平陣列)正規化成前端契約格式,寫到
repo 根目錄 events.json(GitHub Pages 服務的位置)。

為何要這步:爬蟲各自 merge 寫扁平陣列到 Docs/events.json,結構單純、好疊加;
前端 index.html 則吃 {updated_at, events:[...]} 物件,且價格排序靠數字欄 price_min。
本腳本是兩者之間的橋:讀扁平陣列 → 加 price_min(從 price 字串 parse 最低價)
→ 包成物件 → 寫根 events.json。爬蟲與前端各自契約都不必動。

price_min 取字串中所有數字的最小值(早鳥/會員價通常最低,與前端「價格低→高」一致);
無數字則 None(前端排序視為極大值墊底)。

用法:
    python Py/build_site_json.py            # 讀 Docs/events.json 寫 ./events.json
    python Py/build_site_json.py --check    # 只檢查、印統計,不寫檔
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DOCS_JSON = ROOT / "Docs" / "events.json"
SITE_JSON = ROOT / "events.json"

NUM_RE = re.compile(r"\d[\d,]*")


def parse_price_min(price: str) -> Optional[int]:
    """從價格字串取最低數字(早鳥/優惠價)。無數字回 None。"""
    if not price:
        return None
    nums = [int(m.group(0).replace(",", "")) for m in NUM_RE.finditer(price)]
    nums = [n for n in nums if n > 0]
    return min(nums) if nums else None


def build(events: list[dict]) -> dict:
    out_events = []
    for e in events:
        ev = dict(e)
        ev["price_min"] = parse_price_min(e.get("price", ""))
        # 前端 highlights 來源欄名為 highlights_source,爬蟲未產則略過(不杜撰)
        out_events.append(ev)
    out_events.sort(key=lambda e: e.get("date_start") or "9999")
    # 資料更新日 = 所有筆 fetched_at 的最大值,退而求其次留空
    updated = max((e.get("fetched_at") or "" for e in events), default="")
    return {"updated_at": updated, "count": len(out_events), "events": out_events}


def main() -> None:
    ap = argparse.ArgumentParser(description="正規化 Docs/events.json → 根 events.json")
    ap.add_argument("--check", action="store_true", help="只印統計不寫檔")
    args = ap.parse_args()

    if not DOCS_JSON.exists():
        sys.exit(f"找不到 {DOCS_JSON},請先跑爬蟲")
    events = json.loads(DOCS_JSON.read_text(encoding="utf-8"))
    site = build(events)

    priced = sum(1 for e in site["events"] if e["price_min"] is not None)
    print(f"events: {site['count']} | updated_at: {site['updated_at']} | "
          f"有 price_min: {priced}", file=sys.stderr)

    if args.check:
        return
    SITE_JSON.write_text(json.dumps(site, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"已寫入 {SITE_JSON}", file=sys.stderr)


if __name__ == "__main__":
    main()
