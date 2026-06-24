#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_site_json.py
==================
把爬蟲產出的 Docs/events.json(扁平陣列)正規化成前端契約格式,寫到 repo 根
events.json(GitHub Pages 服務的位置);並在每日 build 時靜態生成多頁(SSG):

  events.json        前端契約物件 {updated_at,count,events}
  sitemap.xml        首頁 + 全部子頁 URL
  index.html         注入首頁 JSON-LD(只收即將舉行)與預渲染清單(只收有效活動)
  events/{id}.html   ① 每場有效活動一頁 + 單一 Event JSON-LD + 麵包屑
  facilitators/{}.html ② 每位講師彙整頁 + ItemList
  regions/{}.html    ③ 每個地區彙整頁 + ItemList
  archive/index.html 過期活動歸檔(可索引,但不佔首頁相關性)

為何做 SSG:單頁 SPA 的原始 HTML 只有一個 URL,長尾關鍵字(特定講師/地區/活動)
無專屬落地頁,Event Rich Result 觸發率也低。每日 build 為每場有效活動/每位講師/
每個地區生成獨立靜態頁,收錄頁數 1 → 數十,長尾與主題權威同步上升。詳見
Docs/SatirDaily_SEO_Plan.html。

過期活動分離:以「今天」為界把活動分 upcoming / undated / past。首頁預渲染與
首頁 JSON-LD 只收有效活動(upcoming + undated),past 進 /archive/(仍可索引,
保留長尾,但不稀釋首頁「即將舉行」相關性)。SSG 只為有效活動生成頁,避免大量過期頁。

price_min 取價格字串中所有數字的最小值(早鳥/會員價通常最低,與前端「價格低→高」一致);
無數字則 None(前端排序視為極大值墊底)。

用法:
    python Py/build_site_json.py            # 讀 Docs/events.json,寫根 events.json + 全部子頁
    python Py/build_site_json.py --check    # 只檢查、印統計,不寫檔
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DOCS_JSON = ROOT / "Docs" / "events.json"
SITE_JSON = ROOT / "events.json"
SITEMAP = ROOT / "sitemap.xml"
INDEX_HTML = ROOT / "index.html"

# SSG 產物目錄(每次 build 重建,避免殘留已下架活動的孤兒頁)
EVENTS_DIR = ROOT / "events"
FAC_DIR = ROOT / "facilitators"
REG_DIR = ROOT / "regions"
ARCHIVE_DIR = ROOT / "archive"
OG_DIR = ROOT / "assets" / "og"

# GitHub Pages 服務網址(專案頁)。robots.txt / sitemap / canonical 都指這。
SITE_BASE = "https://guru4tw.github.io/SatirDaily/"

TODAY = datetime.date.today().isoformat()

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

# 講師欄位分隔符:逗號家族 + & + 分號 + 斜線。刻意不切「空白」,避免把
# 「林佳逸 Jerry Lin」這種中英並列的同一人拆成兩個。同名/別名正規化見 §4 風險備註。
FAC_SPLIT_RE = re.compile(r"[,，、&＆;；/]+")


# ──────────────────────────────────────────────────────────────────────
# 共用工具
# ──────────────────────────────────────────────────────────────────────
def parse_price_min(price: str) -> Optional[int]:
    """從價格字串取最低數字(早鳥/優惠價)。無數字回 None。"""
    if not price:
        return None
    nums = [int(m.group(0).replace(",", "")) for m in NUM_RE.finditer(price)]
    nums = [n for n in nums if n > 0]
    return min(nums) if nums else None


def esc(s) -> str:
    """HTML escape(文字節點/屬性值用)。"""
    return (str(s or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def is_past(e: dict) -> bool:
    """活動是否已結束:有 date_start,且結束日(無則開始日)早於今天。"""
    ds = e.get("date_start")
    if not ds:
        return False
    return (e.get("date_end") or ds) < TODAY


def bucket(e: dict) -> str:
    """upcoming(即將舉行)/ undated(無固定日期)/ past(已結束)。與前端 bucketOf 等價。"""
    if not e.get("date_start"):
        return "undated"
    return "past" if is_past(e) else "upcoming"


def slugify(name: str) -> str:
    """講師/地區名 → 檔名安全 slug。保留中日韓字與英數,其餘(空白/標點)轉'-'。
    URL 仍會 percent-encode 中文,故 slug 保留中文可讀。空字串回 'untitled'。"""
    s = (name or "").strip()
    s = re.sub(r"[\s/\\,，、&＆()（）·.。:：;；'\"!！?？]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "untitled"


def split_facilitators(s: str) -> list[str]:
    """把講師欄(可能多人)切成正規化後的單一講師名清單。"""
    if not s:
        return []
    out, seen = [], set()
    for part in FAC_SPLIT_RE.split(s):
        name = part.strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def url_for(path: str) -> str:
    """relative path(如 events/abc.html)→ 絕對正規網址,中文段 percent-encode。"""
    return SITE_BASE + quote(path, safe="/")


def og_url_if_exists(rel_png: str) -> Optional[str]:
    """og 圖存在才回絕對 URL(build_og.py 先跑才有);否則 None(不寫死 404)。"""
    return url_for(rel_png) if (ROOT / rel_png).exists() else None


# ──────────────────────────────────────────────────────────────────────
# 前端契約 events.json
# ──────────────────────────────────────────────────────────────────────
def build(events: list[dict]) -> dict:
    out_events = []
    for e in events:
        ev = dict(e)
        ev["price_min"] = parse_price_min(e.get("price", ""))
        name, home = SOURCE_META.get(e.get("source", ""),
                                     (e.get("source", ""), ""))
        ev["source_name"] = name
        ev["source_url"] = e.get("signup_url") or home
        out_events.append(ev)
    out_events.sort(key=lambda e: e.get("date_start") or "9999")
    updated = max((e.get("fetched_at") or "" for e in events), default="")
    return {"updated_at": updated, "count": len(out_events), "events": out_events}


# ──────────────────────────────────────────────────────────────────────
# JSON-LD 產生器
# ──────────────────────────────────────────────────────────────────────
def event_node(e: dict) -> dict:
    """單筆 schema.org Event 節點(有 date_start 才呼叫)。"""
    ev = {
        "@type": "Event",
        "name": e.get("title") or "薩提爾活動",
        "startDate": e["date_start"],
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
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
    return ev


def build_itemlist(events: list[dict], list_name: str) -> str:
    """有日期者組成 schema.org ItemList<Event> JSON 字串。無日期略過,不杜撰。"""
    items, pos = [], 0
    for e in events:
        if not e.get("date_start"):
            continue
        pos += 1
        items.append({"@type": "ListItem", "position": pos, "item": event_node(e)})
    ld = {
        "@context": "https://schema.org", "@type": "ItemList",
        "name": list_name, "itemListElement": items,
    }
    return json.dumps(ld, ensure_ascii=False)


def breadcrumb_ld(crumbs: list[tuple[str, str]]) -> dict:
    """crumbs = [(名稱, 絕對URL), ...] → BreadcrumbList 節點(置於 @graph 內,不帶 @context)。"""
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(crumbs)
        ],
    }


# ──────────────────────────────────────────────────────────────────────
# 子頁 HTML 外殼(自含 CSS,輕量;品牌色對齊 index.html)
# ──────────────────────────────────────────────────────────────────────
PAGE_CSS = """
:root{--ink:#1f302d;--ink-soft:#5d6f6b;--ink-faint:#647571;--bg:#f1f7f4;
--surface:#fff;--line:#e3ece8;--water:#2c8c84;--water-600:#1f6f68;--water-wash:#dcebe6;
--clay:#d3835c;--serif:"Noto Serif TC",Georgia,serif;--sans:"Noto Sans TC",system-ui,sans-serif;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.75;
-webkit-font-smoothing:antialiased;}
.wrap{max-width:880px;margin:0 auto;padding:0 22px;}
header.top{background:linear-gradient(178deg,var(--water-wash),var(--bg));
border-bottom:1px solid var(--line);padding:26px 0 30px;}
.brand{font-family:var(--serif);font-weight:700;color:var(--water-600);font-size:1.05rem;
text-decoration:none;display:inline-flex;align-items:center;gap:8px;}
.hero-og{display:block;width:100%;height:auto;border-radius:16px;
border:1px solid var(--line);margin:18px 0 4px;box-shadow:var(--shadow-sm,0 1px 2px rgba(31,48,45,.05));}
.crumb{font-size:.82rem;color:var(--ink-faint);margin:14px 0 0;}
.crumb a{color:var(--water);text-decoration:none;}
.crumb a:hover{text-decoration:underline;}
h1{font-family:var(--serif);font-size:1.6rem;line-height:1.35;margin:18px 0 6px;color:var(--ink);}
.sub{color:var(--ink-soft);font-size:.95rem;margin-bottom:4px;}
main{padding:26px 0 56px;}
.when{display:inline-block;background:var(--water-wash);color:var(--water-600);
font-weight:600;font-size:.9rem;padding:4px 12px;border-radius:999px;margin:6px 0 16px;}
.facts{list-style:none;display:grid;gap:8px;margin:14px 0 20px;}
.facts li{color:var(--ink-soft);font-size:.95rem;}
.facts b{color:var(--ink);font-weight:600;}
.facts a{color:var(--water-600);}
.desc{background:var(--surface);border:1px solid var(--line);border-radius:14px;
padding:16px 18px;margin:16px 0;color:var(--ink-soft);white-space:pre-wrap;}
.cta{display:inline-block;background:var(--water-600);color:#fff;font-weight:600;
text-decoration:none;padding:11px 22px;border-radius:12px;margin:8px 0;}
.cta:hover{background:var(--water);}
.back{display:inline-block;margin:8px 12px 8px 0;color:var(--water-600);text-decoration:none;font-size:.9rem;}
.cards{display:grid;gap:14px;margin:18px 0;}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px;}
.card.past{opacity:.7;}
.card h3{font-size:1.05rem;margin-bottom:6px;}
.card h3 a{color:var(--ink);text-decoration:none;}
.card h3 a:hover{color:var(--water-600);}
.card .m{color:var(--ink-faint);font-size:.86rem;margin-top:4px;}
.note{color:var(--ink-faint);font-size:.82rem;margin-top:6px;}
footer{border-top:1px solid var(--line);padding:22px 0 48px;color:var(--ink-faint);font-size:.82rem;}
footer a{color:var(--water-600);}
"""


def page_shell(*, title: str, desc: str, canonical: str, body: str,
               jsonld: str = "", og: Optional[str] = None) -> str:
    """共用頁面外殼。canonical/og 用絕對 URL。"""
    head_og = ""
    if og:
        head_og = (
            f'<meta property="og:image" content="{esc(og)}">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n'
            f'<meta name="twitter:image" content="{esc(og)}">\n'
        )
    ld = (f'<script type="application/ld+json">{jsonld}</script>\n'
          if jsonld else "")
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
{head_og}<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700&family=Noto+Serif+TC:wght@600;700&display=swap" rel="stylesheet">
<style>{PAGE_CSS}</style>
{ld}</head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="{esc(SITE_BASE)}">SatirDaily｜薩提爾活動每日匯整</a>
</div></header>
<main><div class="wrap">
{body}
</div></main>
<footer><div class="wrap">
SatirDaily · 資料每日由 GitHub Actions 自動更新 · 活動資訊以原始報名連結為準。
　<a href="{esc(SITE_BASE)}">回活動總覽 →</a>
</div></footer>
</body>
</html>
"""


def card_html(e: dict, href: str) -> str:
    """彙整頁用的活動小卡(連向該活動的靜態頁或原始頁)。"""
    when = e.get("date_start") or "日期未定"
    if e.get("date_end") and e["date_end"] != e.get("date_start"):
        when = f'{e["date_start"]} ～ {e["date_end"]}'
    meta = " · ".join(filter(None, [
        esc(e.get("region")), esc(e.get("venue")),
        f'帶領:{esc(e["facilitator"])}' if e.get("facilitator") else "",
        f'主辦:{esc(e["organizer"])}' if e.get("organizer") else "",
    ]))
    past = " past" if is_past(e) else ""
    return (
        f'<article class="card{past}">'
        f'<h3><a href="{esc(href)}">{esc(e.get("title") or "薩提爾活動")}</a></h3>'
        f'<p class="when">{esc(when)}</p>'
        + (f'<p class="m">{meta}</p>' if meta else "")
        + "</article>"
    )


# ──────────────────────────────────────────────────────────────────────
# ① 活動頁
# ──────────────────────────────────────────────────────────────────────
def event_page(e: dict) -> str:
    eid = e["id"]
    region = e.get("region") or ""
    fac = e.get("facilitator") or ""
    title_core = e.get("title") or "薩提爾活動"
    year = (e.get("date_start") or "")[:4]
    seo_bits = "・".join(filter(None, [fac, f"{region}薩提爾工作坊" if region else "薩提爾工作坊"]))
    page_title = f"{title_core}｜{seo_bits}{(' ' + year) if year else ''} ｜ SatirDaily"
    desc = (e.get("purpose") or e.get("summary")
            or f"{title_core} — {region}薩提爾工作坊／課程,點此查看日期、地點、帶領者與報名連結。")[:155]
    canonical = url_for(f"events/{eid}.html")

    when = e.get("date_start") or "日期未定"
    if e.get("date_end") and e["date_end"] != e.get("date_start"):
        when = f'{e["date_start"]} ～ {e["date_end"]}'

    facts = []
    if region:
        facts.append(f'<li>地區 <b><a href="{esc(url_for("regions/" + slugify(region) + ".html"))}">{esc(region)}</a></b></li>')
    if e.get("venue"):
        facts.append(f'<li>地點 <b>{esc(e["venue"])}</b></li>')
    for one in split_facilitators(fac):
        facts.append(f'<li>帶領者 <b><a href="{esc(url_for("facilitators/" + slugify(one) + ".html"))}">{esc(one)}</a></b></li>')
    if e.get("organizer"):
        facts.append(f'<li>主辦 <b>{esc(e["organizer"])}</b></li>')
    if e.get("price"):
        facts.append(f'<li>費用 <b>{esc(e["price"])}</b></li>')

    desc_block = ""
    long_desc = e.get("summary") or e.get("purpose")
    if long_desc:
        desc_block = f'<div class="desc">{esc(long_desc)}</div>'

    cta = ""
    if e.get("signup_url"):
        cta = f'<a class="cta" href="{esc(e["signup_url"])}" target="_blank" rel="noopener">我要報名 →</a>'

    src_name, _ = SOURCE_META.get(e.get("source", ""), (e.get("source", ""), ""))
    src = (f'<span class="note">資料更新日 {esc(e.get("fetched_at") or "—")}　·　來源 '
           f'<a href="{esc(e.get("signup_url") or SITE_BASE)}" target="_blank" rel="noopener">{esc(src_name)} ↗</a></span>')

    crumb_links = [("首頁", SITE_BASE)]
    if region:
        crumb_links.append((f"{region}活動", url_for(f"regions/{slugify(region)}.html")))
    crumb_links.append((title_core, canonical))
    crumb_html = " › ".join(
        f'<a href="{esc(u)}">{esc(n)}</a>' if i < len(crumb_links) - 1 else esc(n)
        for i, (n, u) in enumerate(crumb_links)
    )

    og = og_url_if_exists(f"assets/og/{eid}.png")
    hero = f'<img class="hero-og" src="{esc(og)}" alt="{esc(title_core)} 活動摘要圖" width="1200" height="630">' if og else ""

    body = f"""<p class="crumb">{crumb_html}</p>
{hero}
<h1>{esc(title_core)}</h1>
<div class="when">{esc(when)}</div>
<ul class="facts">
{chr(10).join(facts)}
</ul>
{desc_block}
<p>{cta}</p>
{src}
<p style="margin-top:22px">
<a class="back" href="{esc(SITE_BASE)}">← 回活動總覽</a>
{f'<a class="back" href="{esc(url_for("regions/" + slugify(region) + ".html"))}">看更多{esc(region)}活動 →</a>' if region else ''}
</p>"""

    graph = [event_node(e), breadcrumb_ld(crumb_links)] if e.get("date_start") else [breadcrumb_ld(crumb_links)]
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
    return page_shell(title=page_title, desc=desc, canonical=canonical,
                      body=body, jsonld=jsonld, og=og)


# ──────────────────────────────────────────────────────────────────────
# ② 講師頁 / ③ 地區頁(彙整頁共用骨架)
# ──────────────────────────────────────────────────────────────────────
def aggregate_page(*, h1: str, page_title: str, desc: str, canonical: str,
                   crumbs: list[tuple[str, str]], intro: str,
                   events: list[dict], list_name: str) -> str:
    crumb_html = " › ".join(
        f'<a href="{esc(u)}">{esc(n)}</a>' if i < len(crumbs) - 1 else esc(n)
        for i, (n, u) in enumerate(crumbs)
    )
    cards = "\n".join(
        card_html(e, url_for(f"events/{e['id']}.html"))
        for e in events
    )
    body = f"""<p class="crumb">{crumb_html}</p>
<h1>{esc(h1)}</h1>
<p class="sub">{esc(intro)}</p>
<div class="cards">
{cards}
</div>
<p><a class="back" href="{esc(SITE_BASE)}">← 回活動總覽</a></p>"""
    jsonld = build_itemlist(events, list_name)
    og = og_url_if_exists("assets/og/default.png")
    return page_shell(title=page_title, desc=desc, canonical=canonical,
                      body=body, jsonld=jsonld, og=og)


def facilitator_page(name: str, events: list[dict]) -> str:
    slug = slugify(name)
    canonical = url_for(f"facilitators/{slug}.html")
    n = len(events)
    return aggregate_page(
        h1=f"{name}的薩提爾工作坊與課程",
        page_title=f"{name}｜薩提爾工作坊・課程一覽({n}場) ｜ SatirDaily",
        desc=f"{name}帶領的薩提爾模式工作坊、課程與成長活動共 {n} 場,依日期整理,含地點、費用與報名連結。",
        canonical=canonical,
        crumbs=[("首頁", SITE_BASE), ("講師", SITE_BASE), (name, canonical)],
        intro=f"彙整 {name} 帶領的薩提爾相關活動,點各活動看完整資訊與報名連結。",
        events=events, list_name=f"{name}的薩提爾活動")


def region_page(region: str, events: list[dict]) -> str:
    slug = slugify(region)
    canonical = url_for(f"regions/{slug}.html")
    n = len(events)
    return aggregate_page(
        h1=f"{region}的薩提爾工作坊與課程",
        page_title=f"{region}薩提爾工作坊・課程一覽({n}場) ｜ SatirDaily",
        desc=f"{region}地區的薩提爾模式工作坊、課程與成長團體共 {n} 場,依日期整理,含帶領者、費用與報名連結。",
        canonical=canonical,
        crumbs=[("首頁", SITE_BASE), ("地區", SITE_BASE), (region, canonical)],
        intro=f"彙整在 {region} 舉辦的薩提爾相關活動,點各活動看完整資訊與報名連結。",
        events=events, list_name=f"{region}的薩提爾活動")


def archive_page(past: list[dict]) -> str:
    canonical = url_for("archive/index.html")
    # 歸檔頁連回原始活動頁(過期活動不另生成靜態頁)
    cards = "\n".join(
        card_html(e, e.get("signup_url") or e.get("source_url") or SITE_BASE)
        for e in sorted(past, key=lambda e: e.get("date_start") or "", reverse=True)
    )
    body = f"""<p class="crumb"><a href="{esc(SITE_BASE)}">首頁</a> › 歷史歸檔</p>
<h1>已結束的薩提爾活動(歷史歸檔)</h1>
<p class="sub">以下活動已結束,僅供回顧參考。最新可報名的活動請見 <a href="{esc(SITE_BASE)}">活動總覽</a>。</p>
<div class="cards">
{cards}
</div>
<p><a class="back" href="{esc(SITE_BASE)}">← 回活動總覽</a></p>"""
    return page_shell(
        title="薩提爾活動歷史歸檔 ｜ SatirDaily",
        desc="SatirDaily 已結束薩提爾工作坊與課程的歷史歸檔,供回顧參考。",
        canonical=canonical, body=body)


# ──────────────────────────────────────────────────────────────────────
# sitemap / 首頁注入
# ──────────────────────────────────────────────────────────────────────
def write_sitemap(updated: str, urls: list[tuple[str, str, str]]) -> None:
    """urls = [(絕對URL, changefreq, priority), ...]。首頁排第一。"""
    lastmod = f"    <lastmod>{updated}</lastmod>\n" if updated else ""
    body = []
    for loc, freq, prio in urls:
        body.append(
            "  <url>\n"
            f"    <loc>{esc(loc)}</loc>\n"
            f"{lastmod}"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{prio}</priority>\n"
            "  </url>\n"
        )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(body) + "</urlset>\n")
    SITEMAP.write_text(xml, encoding="utf-8")


def build_prerender(events: list[dict]) -> str:
    """首頁預渲染清單(Googlebot 抓原始 HTML 看到的內容)。卡片標題連向該活動的
    靜態頁(events/{id}.html),讓爬蟲發現長尾 URL;JS 載入後以互動版覆寫 #list。
    只收有效活動(已由呼叫端過濾)。"""
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
        href = f"events/{quote(e['id'], safe='')}.html"
        title = esc(e.get("title") or "薩提爾活動")
        rows.append(
            f'<article class="card"><h3><a href="{href}">{title}</a></h3>'
            f'<p class="when">{esc(when)}</p>'
            + (f'<p class="meta">{meta}</p>' if meta else "")
            + "</article>"
        )
    return "\n".join(rows)


def inject_index(jsonld: str, prerender: str) -> bool:
    """把首頁 JSON-LD 與預渲染清單寫進 index.html 的標記區。回傳是否有改動。"""
    if not INDEX_HTML.exists():
        print(f"略過注入:找不到 {INDEX_HTML}", file=sys.stderr)
        return False
    html = INDEX_HTML.read_text(encoding="utf-8")
    orig = html
    html = re.sub(
        r'(<script type="application/ld\+json" id="ld-events">).*?(</script>)',
        lambda m: m.group(1) + jsonld + m.group(2),
        html, count=1, flags=re.DOTALL,
    )
    html = re.sub(
        r"(<!--PRERENDER:START-->).*?(<!--PRERENDER:END-->)",
        lambda m: m.group(1) + "\n" + prerender + "\n" + m.group(2),
        html, count=1, flags=re.DOTALL,
    )
    if html != orig:
        INDEX_HTML.write_text(html, encoding="utf-8")
        return True
    return False


# ──────────────────────────────────────────────────────────────────────
# SSG 主流程
# ──────────────────────────────────────────────────────────────────────
def _reset_dir(d: Path) -> None:
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)


def build_pages(events: list[dict]) -> dict:
    """生成全部子頁,回傳 {各類 URL 清單} 供 sitemap 用。
    events 為已正規化(含 source_url 等)的全量清單。"""
    upcoming = [e for e in events if bucket(e) == "upcoming"]
    undated = [e for e in events if bucket(e) == "undated"]
    past = [e for e in events if bucket(e) == "past"]
    active = upcoming + undated  # 有效活動 = 可報名(即將舉行 + 隨到隨學)

    # 乾淨重建,避免下架活動留孤兒頁
    for d in (EVENTS_DIR, FAC_DIR, REG_DIR, ARCHIVE_DIR):
        _reset_dir(d)

    event_urls, fac_urls, reg_urls = [], [], []

    # ① 活動頁(只為有效活動)
    for e in active:
        (EVENTS_DIR / f"{e['id']}.html").write_text(event_page(e), encoding="utf-8")
        event_urls.append(url_for(f"events/{e['id']}.html"))

    # ② 講師頁(把多人欄拆開後分組,只計有效活動)
    fac_map: dict[str, list[dict]] = {}
    for e in active:
        for name in split_facilitators(e.get("facilitator", "")):
            fac_map.setdefault(name, []).append(e)
    for name, evs in fac_map.items():
        evs.sort(key=lambda e: e.get("date_start") or "9999")
        slug = slugify(name)
        (FAC_DIR / f"{slug}.html").write_text(facilitator_page(name, evs), encoding="utf-8")
        fac_urls.append(url_for(f"facilitators/{slug}.html"))

    # ③ 地區頁(只計有效活動,排除「線上/—」等無地區聚合意義者由資料決定)
    reg_map: dict[str, list[dict]] = {}
    for e in active:
        r = (e.get("region") or "").strip()
        if r and r != "—":
            reg_map.setdefault(r, []).append(e)
    for region, evs in reg_map.items():
        evs.sort(key=lambda e: e.get("date_start") or "9999")
        slug = slugify(region)
        (REG_DIR / f"{slug}.html").write_text(region_page(region, evs), encoding="utf-8")
        reg_urls.append(url_for(f"regions/{slug}.html"))

    # 歸檔頁
    (ARCHIVE_DIR / "index.html").write_text(archive_page(past), encoding="utf-8")

    return {
        "active": active, "past": past,
        "event_urls": event_urls, "fac_urls": fac_urls, "reg_urls": reg_urls,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="正規化 Docs/events.json → 根 events.json + SSG 子頁")
    ap.add_argument("--check", action="store_true", help="只印統計不寫檔")
    args = ap.parse_args()

    if not DOCS_JSON.exists():
        sys.exit(f"找不到 {DOCS_JSON},請先跑爬蟲")
    events = json.loads(DOCS_JSON.read_text(encoding="utf-8"))
    site = build(events)
    evs = site["events"]

    n_up = sum(1 for e in evs if bucket(e) == "upcoming")
    n_un = sum(1 for e in evs if bucket(e) == "undated")
    n_pa = sum(1 for e in evs if bucket(e) == "past")
    priced = sum(1 for e in evs if e["price_min"] is not None)
    print(f"events: {site['count']} | updated_at: {site['updated_at']} | "
          f"有 price_min: {priced} | upcoming:{n_up} undated:{n_un} past:{n_pa}",
          file=sys.stderr)

    if args.check:
        return

    # 1) 前端契約
    SITE_JSON.write_text(json.dumps(site, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2) SSG 子頁
    pages = build_pages(evs)
    active = pages["active"]

    # 3) 首頁注入:JSON-LD 只收即將舉行(有日期);預渲染只收有效活動
    upcoming_dated = [e for e in active if bucket(e) == "upcoming"]
    changed = inject_index(build_itemlist(upcoming_dated, "全台薩提爾活動清單"),
                           build_prerender(active))

    # 4) sitemap:首頁 + 活動頁 + 講師頁 + 地區頁 + 歸檔頁
    urls = [(SITE_BASE, "daily", "1.0")]
    urls += [(u, "weekly", "0.8") for u in pages["event_urls"]]
    urls += [(u, "weekly", "0.6") for u in pages["fac_urls"]]
    urls += [(u, "weekly", "0.6") for u in pages["reg_urls"]]
    urls.append((url_for("archive/index.html"), "monthly", "0.4"))
    write_sitemap(site["updated_at"], urls)

    print(f"已寫入 {SITE_JSON} 與 {SITEMAP}"
          f"{';並更新 index.html 預渲染' if changed else ''}\n"
          f"  子頁:活動 {len(pages['event_urls'])} / 講師 {len(pages['fac_urls'])} / "
          f"地區 {len(pages['reg_urls'])} / 歸檔 1(past {len(pages['past'])})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
