#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_links.py
===============
獨立的「原始活動連結」驗證器。每天重建 events.json 後跑這支,逐筆連回活動的
原始頁面(signup_url),確認連結仍有效,把結果寫回資料並產出報告。

為何獨立成一支:抓資料(各 crawler)與「驗證連結是否還活著」是兩件事,職責分開
才好維護 — 爬蟲壞掉不影響驗證,驗證規則改動也不必動爬蟲。pipeline 串成
    crawl → build_site_json → verify_links → commit
即可確保上線的每筆活動連結都被檢查過。

做法:
    1. 讀 Docs/events.json(扁平陣列)
    2. 逐筆對 signup_url 發請求(先 HEAD,不被支援再 GET),沿用 SatirEventBot UA
       與請求間延遲,友善爬取
    3. 判定:2xx/3xx = ok;4xx/5xx/逾時/連線失敗 = broken;無 signup_url = skipped
    4. 把 link_ok(bool)與 link_checked_at(日期)寫回每筆(--annotate,預設開)
    5. 產出報告 Docs/link_report.json(摘要 + 每筆狀態),broken 清單同時印到 stderr
    6. exit code:全通過 0;有 broken 2;讀檔失敗 1 — 給 CI 判斷是否擋上線

用法:
    python Py/verify_links.py                 # 驗證 + 回寫 Docs/events.json + 出報告
    python Py/verify_links.py --no-annotate   # 只驗證出報告,不改 events.json
    python Py/verify_links.py --timeout 15    # 改逾時(預設 12 秒)
    python Py/verify_links.py --fail-fast     # 遇第一個 broken 即停(除錯用)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DOCS_JSON = ROOT / "Docs" / "events.json"
REPORT_JSON = ROOT / "Docs" / "link_report.json"

try:
    import requests
except ImportError:
    sys.exit("缺少套件 requests,請先執行:pip install requests")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SatirEventBot/1.0; "
        "+https://github.com/guru4tw/SatirDaily)"
    )
}
REQUEST_DELAY = 0.8        # 友善延遲(秒),沿用專案慣例
DEFAULT_TIMEOUT = 12


@dataclass
class LinkResult:
    id: str
    title: str
    source: str
    url: str
    status: str            # ok / broken / skipped
    http: Optional[int]    # HTTP 狀態碼(無則 None)
    note: str              # 失敗原因或最終導向


def check_url(url: str, timeout: int) -> tuple[str, Optional[int], str]:
    """回 (status, http_code, note)。先 HEAD,部分站不支援(405/403)再 GET。"""
    if not url:
        return ("skipped", None, "無 signup_url")
    try:
        resp = requests.head(url, headers=HEADERS, timeout=timeout,
                             allow_redirects=True)
        if resp.status_code in (403, 405, 501) or resp.status_code >= 400:
            # HEAD 不被支援或被擋,改用 GET(只讀少量)再判一次
            resp = requests.get(url, headers=HEADERS, timeout=timeout,
                                allow_redirects=True, stream=True)
            resp.close()
        code = resp.status_code
        final = resp.url
        if 200 <= code < 400:
            note = f"→ {final}" if final != url else ""
            return ("ok", code, note)
        return ("broken", code, f"HTTP {code}")
    except requests.Timeout:
        return ("broken", None, f"逾時 ({timeout}s)")
    except requests.RequestException as exc:
        return ("broken", None, type(exc).__name__)
    finally:
        time.sleep(REQUEST_DELAY)


def verify(events: list[dict], timeout: int,
           fail_fast: bool) -> list[LinkResult]:
    results: list[LinkResult] = []
    total = len(events)
    for i, ev in enumerate(events, 1):
        url = ev.get("signup_url", "")
        status, code, note = check_url(url, timeout)
        results.append(LinkResult(
            id=ev.get("id", ""),
            title=ev.get("title", ""),
            source=ev.get("source", ""),
            url=url,
            status=status,
            http=code,
            note=note,
        ))
        tag = {"ok": "OK", "broken": "BROKEN", "skipped": "SKIP"}[status]
        print(f"  [{i}/{total}] {tag:6} {ev.get('id','')} {url} {note}",
              file=sys.stderr)
        if fail_fast and status == "broken":
            print("  --fail-fast:遇 broken 即停", file=sys.stderr)
            break
    return results


def annotate(events: list[dict], results: list[LinkResult],
             checked_at: str) -> None:
    """把驗證結果寫回每筆:link_ok(bool/None)+ link_checked_at。"""
    by_id = {r.id: r for r in results}
    for ev in events:
        r = by_id.get(ev.get("id", ""))
        if r is None:
            continue
        ev["link_ok"] = (True if r.status == "ok"
                         else False if r.status == "broken" else None)
        ev["link_checked_at"] = checked_at


def main() -> int:
    ap = argparse.ArgumentParser(description="驗證 events.json 內每筆原始活動連結")
    ap.add_argument("--no-annotate", action="store_true",
                    help="只出報告,不把 link_ok 寫回 Docs/events.json")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"HTTP 逾時秒數(預設 {DEFAULT_TIMEOUT})")
    ap.add_argument("--fail-fast", action="store_true",
                    help="遇第一個 broken 即停(除錯用)")
    args = ap.parse_args()

    if not DOCS_JSON.exists():
        print(f"找不到 {DOCS_JSON},請先跑爬蟲", file=sys.stderr)
        return 1
    try:
        events = json.loads(DOCS_JSON.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        print(f"讀取 {DOCS_JSON} 失敗:{exc}", file=sys.stderr)
        return 1

    checked_at = dt.datetime.now().strftime("%Y-%m-%d")
    print(f"[verify] 開始驗證 {len(events)} 筆連結", file=sys.stderr)
    results = verify(events, args.timeout, args.fail_fast)

    ok = sum(1 for r in results if r.status == "ok")
    broken = [r for r in results if r.status == "broken"]
    skipped = sum(1 for r in results if r.status == "skipped")

    report = {
        "checked_at": checked_at,
        "total": len(results),
        "ok": ok,
        "broken": len(broken),
        "skipped": skipped,
        "broken_list": [asdict(r) for r in broken],
        "results": [asdict(r) for r in results],
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"[verify] ok {ok} / broken {len(broken)} / skip {skipped}"
          f" — 報告寫入 {REPORT_JSON}", file=sys.stderr)

    if broken:
        print("[verify] BROKEN 連結:", file=sys.stderr)
        for r in broken:
            print(f"    {r.id} {r.url} ({r.note})", file=sys.stderr)

    if not args.no_annotate:
        annotate(events, results, checked_at)
        DOCS_JSON.write_text(json.dumps(events, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"[verify] 已回寫 link_ok / link_checked_at → {DOCS_JSON}",
              file=sys.stderr)

    return 2 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
