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
SITEMAP = ROOT / "sitemap.xml"
INDEX_HTML = ROOT / "index.html"

# GitHub Pages 服務網址(專案頁)。robots.txt 與 sitemap 的 <loc> 都指這。
SITE_BASE = "https://guru4tw.github.io/SatirDaily/"

NUM_RE = re.compile(r"\d[\d,]*")

# 來源 key → (顯示名稱, 機構首頁)。爬蟲只存 source key,前端要顯示中文名與可點首頁,
# 在此集中對照。新增爬蟲時補一筆即可,缺項則退回 key 本身與空首頁。
SOURCE_META = {
    "lopwilldo": ("長耳兔心靈維度", "https://lopwilldo.com"),
    "shiuhli":   ("旭立文教基金會", "https://www.shiuhli.org.tw"),
    "comflow":   ("心流逸境教育平台", "https://comflow.tw"),
    "satir_org": ("台灣薩提爾成長模式推展協會", "https://www.satir.org.tw"),
    "omia":      ("OMIA 學東西", "https://www.omia.com.tw"),
}


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
        # 來源顯示名與「原始活動連結」:前端卡片把「來源」做成可點連結,直接連回
        # 該活動的原始頁面(signup_url);無 signup_url 時退回機構首頁。
        name, home = SOURCE_META.get(e.get("source", ""),
                                     (e.get("source", ""), ""))
        ev["source_name"] = name
        ev["source_url"] = e.get("signup_url") or home
        # 前端 highlights 來源欄名為 highlights_source,爬蟲未產則略過(不杜撰)
        out_events.append(ev)
    out_events.sort(key=lambda e: e.get("date_start") or "9999")
    # 資料更新日 = 所有筆 fetched_at 的最大值,退而求其次留空
    updated = max((e.get("fetched_at") or "" for e in events), default="")
    return {"updated_at": updated, "count": len(out_events), "events": out_events}


def write_sitemap(updated: str) -> None:
    """產 sitemap.xml。前端為單頁 SPA(所有活動同頁渲染),故只列首頁一條 URL,
    lastmod 取資料更新日,changefreq daily,讓 Google 提高爬取頻率。"""
    lastmod = f"    <lastmod>{updated}</lastmod>\n" if updated else ""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{SITE_BASE}</loc>\n"
        f"{lastmod}"
        "    <changefreq>daily</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "</urlset>\n"
    )
    SITEMAP.write_text(xml, encoding="utf-8")


def esc(s) -> str:
    """HTML escape(預渲染文字用)。"""
    return (str(s or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def build_jsonld(events: list[dict]) -> str:
    """產 schema.org ItemList<Event> JSON 字串(伺服器端版本,與前端 injectJsonLd 等價)。
    只收有 date_start 者(Event 必填 startDate);無日期者略過,不杜撰。"""
    items = []
    pos = 0
    for e in events:
        if not e.get("date_start"):
            continue
        pos += 1
        ev = {
            "@type": "Event",
            "name": e.get("title") or "薩提爾活動",
            "startDate": e["date_start"],
            "eventStatus": "https://schema.org/EventScheduled",
            "location": {
                "@type": "Place",
                "name": e.get("venue") or e.get("region") or "台灣",
                "address": e.get("region") or e.get("venue") or "台灣",
            },
        }
        if e.get("date_end"):
            ev["endDate"] = e["date_end"]
        desc = e.get("purpose") or e.get("summary")
        if desc:
            ev["description"] = str(desc)[:300]
        if e.get("signup_url"):
            ev["url"] = e["signup_url"]
        if e.get("organizer"):
            ev["organizer"] = {"@type": "Organization", "name": e["organizer"]}
        if e.get("facilitator"):
            ev["performer"] = {"@type": "Person", "name": e["facilitator"]}
        if e.get("price_min") is not None:
            ev["offers"] = {
                "@type": "Offer", "price": e["price_min"], "priceCurrency": "TWD",
                "url": e.get("signup_url") or SITE_BASE,
                "availability": "https://schema.org/InStock",
            }
        items.append({"@type": "ListItem", "position": pos, "item": ev})
    ld = {
        "@context": "https://schema.org", "@type": "ItemList",
        "name": "全台薩提爾活動清單", "itemListElement": items,
    }
    return json.dumps(ld, ensure_ascii=False)


def build_prerender(events: list[dict]) -> str:
    """產可索引的活動清單 HTML(無 JS 時的 fallback,也是 Googlebot 抓原始 HTML 看到的內容)。
    前端 JS 載入後會以互動版覆寫 #list,故此處只求語意清楚、含關鍵欄位。"""
    rows = []
    for e in events:
        when = e.get("date_start") or "日期未定"
        if e.get("date_end") and e.get("date_end") != e.get("date_start"):
            when = f'{e["date_start"]} ～ {e["date_end"]}'
        meta = " · ".join(filter(None, [
            esc(e.get("region")), esc(e.get("venue")),
            f'帶領:{esc(e["facilitator"])}' if e.get("facilitator") else "",
            f'主辦:{esc(e["organizer"])}' if e.get("organizer") else "",
        ]))
        url = e.get("signup_url") or e.get("source_url") or ""
        title = esc(e.get("title") or "薩提爾活動")
        link = (f'<a href="{esc(url)}" rel="noopener nofollow">{title}</a>'
                if url else title)
        rows.append(
            f'<article class="card"><h3>{link}</h3>'
            f'<p class="when">{esc(when)}</p>'
            + (f'<p class="meta">{meta}</p>' if meta else "")
            + "</article>"
        )
    return "\n".join(rows)


def inject_index(jsonld: str, prerender: str) -> bool:
    """把 JSON-LD 與預渲染清單寫進 index.html 的標記區。回傳是否有改動。"""
    if not INDEX_HTML.exists():
        print(f"略過注入:找不到 {INDEX_HTML}", file=sys.stderr)
        return False
    html = INDEX_HTML.read_text(encoding="utf-8")
    orig = html
    # 1) JSON-LD:替換 id="ld-events" script 的內容
    html = re.sub(
        r'(<script type="application/ld\+json" id="ld-events">).*?(</script>)',
        lambda m: m.group(1) + jsonld + m.group(2),
        html, count=1, flags=re.DOTALL,
    )
    # 2) 預渲染清單:替換 PRERENDER 標記之間的內容
    html = re.sub(
        r"(<!--PRERENDER:START-->).*?(<!--PRERENDER:END-->)",
        lambda m: m.group(1) + "\n" + prerender + "\n" + m.group(2),
        html, count=1, flags=re.DOTALL,
    )
    if html != orig:
        INDEX_HTML.write_text(html, encoding="utf-8")
        return True
    return False


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
    write_sitemap(site["updated_at"])
    changed = inject_index(build_jsonld(site["events"]),
                           build_prerender(site["events"]))
    print(f"已寫入 {SITE_JSON} 與 {SITEMAP}"
          f"{';並更新 index.html 預渲染' if changed else ''}", file=sys.stderr)


if __name__ == "__main__":
    main()
